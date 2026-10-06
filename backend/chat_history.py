"""Chat memory for logged-in customers, stored in the existing `chat_messages` table.

    chat_messages(id, user_id, role, content, products_json, created_at)

- One row per message: the customer's question (role "user", products_json NULL) and the
  assistant's answer (role "assistant", products_json = the product cards shown with it).
- Only logged-in customers are stored (user_id is NOT NULL in the schema). Guests can chat,
  but nothing is written.
- The table structure is unchanged; rows are only added. The 22 rows that came with the
  database use the same columns, and their products_json items carry `product_id`, so they
  reload the same way.
- On reload, cards are rebuilt from the database by product_id, so a reloaded card shows
  today's price and stock, not the numbers from the day of the chat.
"""

import json
import re

from db import connect_readonly, connect_writable
from models import CustomerProfile

AGENT_HISTORY_MESSAGES = 20  # earlier messages given to the agent as context
PANEL_HISTORY_MESSAGES = 60  # earlier messages shown when the chat panel reloads


def save_turn(user_id: int, question: str, answer: str, cards: list[dict]) -> None:
    """Store one question and its answer together (both or neither)."""
    with connect_writable() as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, 'user', ?, NULL)",
            (user_id, question),
        )
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, 'assistant', ?, ?)",
            (user_id, answer, json.dumps(cards)),
        )


def load_messages(user_id: int, limit: int) -> list[dict]:
    """The customer's most recent messages, oldest first."""
    with connect_readonly() as conn:
        rows = conn.execute(
            "SELECT role, content, products_json, created_at FROM chat_messages "
            "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def count_messages(user_id: int) -> int:
    with connect_readonly() as conn:
        return conn.execute("SELECT COUNT(*) FROM chat_messages WHERE user_id = ?", (user_id,)).fetchone()[0]


def product_ids_of(products_json: str | None) -> list[str]:
    """Product ids from a stored products_json (ours or the original rows' format)."""
    if not products_json:
        return []
    try:
        items = json.loads(products_json)
    except ValueError:
        return []
    return [item["product_id"] for item in items if isinstance(item, dict) and "product_id" in item]


def plain_text(content: str) -> str:
    """The original rows contain markdown bold (**$68**); the chat panel shows plain text."""
    return re.sub(r"\*\*(.+?)\*\*", r"\1", content)


def customer_profile(user: dict) -> CustomerProfile:
    """The customer fields the agent may see, read from `users`. No password hash, no user id."""
    with connect_readonly() as conn:
        row = conn.execute("SELECT created_at FROM users WHERE id = ?", (user["id"],)).fetchone()
    return CustomerProfile(
        first_name=user["first_name"],
        last_name=user["last_name"],
        email=user["email"],
        member_since=(row["created_at"] or "")[:10] if row else "",
        saved_messages=count_messages(user["id"]),
    )
