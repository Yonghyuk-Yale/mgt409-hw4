"""Print the `users` table so you can see which accounts exist.

Run from the HW 4 folder:
    .venv/Scripts/python.exe backend/show_users.py

Only the first characters of each password hash are shown — enough to see the format
(and that no plain-text password is stored), not enough to be useful to anyone.
"""

from db import DB_PATH, connect_readonly

with connect_readonly() as conn:
    rows = conn.execute(
        "SELECT id, first_name, last_name, email, created_at, password_hash FROM users ORDER BY id"
    ).fetchall()

print(f"users table in {DB_PATH} — {len(rows)} accounts\n")
print(f"{'id':>3}  {'first':<10} {'last':<12} {'email':<34} {'created (UTC)':<20} password_hash")
for row in rows:
    parts = row["password_hash"].split("$")
    scheme = f"{parts[0]}${parts[1]}$" if len(parts) == 4 else f"{parts[0]}$"
    print(
        f"{row['id']:>3}  {row['first_name'] or '':<10} {row['last_name'] or '':<12} "
        f"{row['email']:<34} {row['created_at']:<20} {scheme}…"
    )
