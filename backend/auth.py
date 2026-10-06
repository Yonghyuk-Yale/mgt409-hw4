"""Accounts: sign-up, log-in, log-out, and "who am I".

Passwords
- Never stored. Only a salted PBKDF2-HMAC-SHA256 hash is written to `users.password_hash`.
- New accounts: `pbkdf2_sha256$600000$<salt>$<hash>` — 600,000 iterations (OWASP 2023
  guidance for PBKDF2-SHA256) and a fresh 16-byte random salt per user.
- Accounts that came with the database use `pbkdf2_sha256$<salt>$<hash>` with 120,000
  iterations. They are still verified as-is; their rows are never rewritten.
- Hashes are compared in constant time, and a log-in for an unknown email still runs one
  hash so response time does not reveal which emails exist.

Sessions
- After sign-up or log-in the server sets an HttpOnly cookie holding `<user id + expiry>`
  signed with HMAC-SHA256. JavaScript cannot read it, and it cannot be forged without
  SESSION_SECRET. Each request re-reads the user from the database.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from db import connect_readonly, connect_writable

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000
LEGACY_ITERATIONS = 120_000  # the format shipped in campus_customs.db does not record it
SALT_BYTES = 16

PASSWORD_MIN, PASSWORD_MAX = 8, 128
NAME_MAX, EMAIL_MAX = 50, 254
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# A short deny-list of the passwords attackers try first.
COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890",
    "qwerty123", "qwertyuiop", "11111111", "00000000", "iloveyou", "letmein1",
    "abc12345", "yale1701", "bulldogs", "boolaboola",
}

SESSION_COOKIE = "cc_session"
SESSION_SECONDS = 7 * 24 * 3600
# If SESSION_SECRET is not set, a random one is made at start-up: still unforgeable,
# but everyone is logged out when the server restarts.
SESSION_SECRET = os.getenv("SESSION_SECRET") or secrets.token_urlsafe(32)

MAX_FAILURES, FAILURE_WINDOW = 5, 15 * 60
_failures: dict[str, deque] = defaultdict(deque)

router = APIRouter(prefix="/api/auth")


# ---------- password hashing ----------

def _pbkdf2(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(SALT_BYTES)
    return f"{ALGORITHM}${ITERATIONS}${salt}${_pbkdf2(password, salt, ITERATIONS)}"


def verify_password(password: str, stored: str) -> bool:
    parts = stored.split("$")
    if len(parts) == 4 and parts[0] == ALGORITHM and parts[1].isdigit():
        iterations, salt, expected = int(parts[1]), parts[2], parts[3]
    elif len(parts) == 3 and parts[0] == ALGORITHM:
        iterations, salt, expected = LEGACY_ITERATIONS, parts[1], parts[2]
    else:
        return False
    return hmac.compare_digest(_pbkdf2(password, salt, iterations), expected)


_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


# ---------- session cookie ----------

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str) -> str:
    return _b64(hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).digest())


def make_session_token(user_id: int) -> str:
    payload = _b64(json.dumps({"uid": user_id, "exp": int(time.time()) + SESSION_SECONDS}).encode())
    return f"{payload}.{_sign(payload)}"


def read_session_token(token: str | None) -> int | None:
    if not token or "." not in token:
        return None
    payload, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    try:
        data = json.loads(_unb64(payload))
    except ValueError:
        return None
    if data.get("exp", 0) < time.time():
        return None
    return data.get("uid")


def _set_session(response: Response, user_id: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        make_session_token(user_id),
        max_age=SESSION_SECONDS,
        httponly=True,
        samesite="lax",
        secure=os.getenv("COOKIE_SECURE") == "1",  # set to 1 when served over HTTPS
        path="/",
    )


# ---------- helpers ----------

class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def normalize_email(email: str) -> str:
    return email.strip().lower()


def public_user(row: sqlite3.Row) -> dict:
    """The only user fields that ever leave the server. Never the password hash."""
    first = row["first_name"] or row["name"].split(" ")[0]
    return {
        "id": row["id"],
        "first_name": first,
        "last_name": row["last_name"] or "",
        "name": row["name"],
        "email": row["email"],
    }


def find_user_by_email(email: str) -> sqlite3.Row | None:
    with connect_readonly() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE lower(email) = ?", (normalize_email(email),)
        ).fetchone()


def current_user(request: Request) -> dict | None:
    """Return the logged-in user for this request, or None."""
    user_id = read_session_token(request.cookies.get(SESSION_COOKIE))
    if user_id is None:
        return None
    with connect_readonly() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return public_user(row) if row else None


def _too_many_failures(key: str) -> bool:
    attempts = _failures[key]
    while attempts and attempts[0] < time.time() - FAILURE_WINDOW:
        attempts.popleft()
    return len(attempts) >= MAX_FAILURES


def validate_signup(body: SignupRequest) -> tuple[str, str, str]:
    first, last = body.first_name.strip(), body.last_name.strip()
    email = normalize_email(body.email)
    if not first or not last:
        raise HTTPException(400, "Please enter your first and last name.")
    if len(first) > NAME_MAX or len(last) > NAME_MAX:
        raise HTTPException(400, f"Names can be at most {NAME_MAX} characters.")
    if len(email) > EMAIL_MAX or not EMAIL_PATTERN.match(email):
        raise HTTPException(400, "Please enter a valid email address.")
    if body.password != body.confirm_password:
        raise HTTPException(400, "Passwords do not match.")
    if not PASSWORD_MIN <= len(body.password) <= PASSWORD_MAX:
        raise HTTPException(400, f"Password must be {PASSWORD_MIN}–{PASSWORD_MAX} characters.")
    if body.password.lower() in COMMON_PASSWORDS:
        raise HTTPException(400, "That password is too common. Please choose another.")
    if body.password.lower() == email or body.password.lower() == email.split("@")[0]:
        raise HTTPException(400, "Password can't be your email address.")
    return first, last, email


# ---------- endpoints ----------

@router.post("/signup", status_code=201)
def signup(body: SignupRequest, response: Response) -> dict:
    first, last, email = validate_signup(body)
    if find_user_by_email(email):
        raise HTTPException(409, "An account with this email already exists. Try logging in.")
    try:
        with connect_writable() as conn:
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash, first_name, last_name) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"{first} {last}", email, hash_password(body.password), first, last),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:  # two sign-ups with the same email at once
        raise HTTPException(409, "An account with this email already exists. Try logging in.")
    _set_session(response, row["id"])
    return public_user(row)


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response) -> dict:
    email = normalize_email(body.email)
    key = f"{request.client.host if request.client else '?'}|{email}"
    if _too_many_failures(key):
        raise HTTPException(429, "Too many failed attempts. Please wait 15 minutes and try again.")

    row = find_user_by_email(email) if len(body.password) <= PASSWORD_MAX else None
    stored = row["password_hash"] if row else _DUMMY_HASH
    if not verify_password(body.password[:PASSWORD_MAX], stored) or row is None:
        _failures[key].append(time.time())
        # Same message whether the email or the password was wrong.
        raise HTTPException(401, "Incorrect email or password.")

    _failures.pop(key, None)
    _set_session(response, row["id"])
    return public_user(row)


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request) -> dict | None:
    """The logged-in user, or null for a visitor (not an error — most visitors are anonymous)."""
    return current_user(request)
