"""SQLite connections for the Campus Customs backend.

The catalogue and inventory are read through a read-only connection so the API can never
change them. Only the account code opens a writable connection, and only to add rows to
`users` (the schema and existing rows are never modified).

The database and product images are not in the repository. Unzip data.zip so that
`data/campus_customs.db` and `data/products/` exist in the project folder (next to
`backend/`) or inside `backend/`. CAMPUS_CUSTOMS_DB can point somewhere else.
"""

import os
import sqlite3
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
ROOT = BACKEND_DIR.parent


def _find_data_dir() -> Path:
    if os.getenv("CAMPUS_CUSTOMS_DB"):
        return Path(os.environ["CAMPUS_CUSTOMS_DB"]).resolve().parent
    for candidate in (ROOT / "data", BACKEND_DIR / "data"):
        if (candidate / "campus_customs.db").is_file():
            return candidate
    raise RuntimeError(
        "\n\nCampus Customs data not found.\n"
        f"Unzip data.zip so that this file exists:\n    {ROOT / 'data' / 'campus_customs.db'}\n"
        "(the database and product images are not committed to the repository)\n"
    )


DATA_DIR = _find_data_dir()
DB_PATH = Path(os.getenv("CAMPUS_CUSTOMS_DB", DATA_DIR / "campus_customs.db"))
# Images normally sit next to the database; if the database was pointed elsewhere
# (e.g. a test copy), fall back to the project's data/products folder.
IMAGE_DIR = next(
    (d for d in (DATA_DIR / "products", ROOT / "data" / "products", BACKEND_DIR / "data" / "products") if d.is_dir()),
    DATA_DIR / "products",
)
# White-background copies of the photos (images.py). Inside data/, so never committed.
WHITE_IMAGE_DIR = IMAGE_DIR.parent / "products_white"


def connect_readonly() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def connect_writable() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
