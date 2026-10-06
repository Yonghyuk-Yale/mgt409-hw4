"""Campus Customs API — products, images, accounts, and the chat agent.

- Problem 3: products and images (data rules live in catalogue.py)
- Problem 4: accounts (auth.py)
- Problem 5: POST /api/chat → the PydanticAI agent (agent.py, tools.py, models.py, prompts/prompt.md)
- Problem 8: chat memory for logged-in customers (chat_history.py) and page context
- Problem 9: white-background photos (images.py), Products page filters (GET /api/products/browse)

Run from the backend folder (with the HW 4 .venv active):
    uvicorn main:app --reload --port 8000
or without activating it:
    ..\\.venv\\Scripts\\python.exe -m uvicorn main:app --reload --port 8000
"""

import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load .env (project folder first, then parent folders) before importing modules that read it.
for _directory in (Path(__file__).resolve().parent, *Path(__file__).resolve().parents):
    if (_directory / ".env").is_file():
        load_dotenv(_directory / ".env", override=False)

import uvicorn  # noqa: E402
from fastapi import FastAPI, HTTPException, Query, Request  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from pydantic_ai.exceptions import UsageLimitExceeded  # noqa: E402

import agent  # noqa: E402
import auth  # noqa: E402
import catalogue  # noqa: E402
import chat_history  # noqa: E402
import images  # noqa: E402
from db import IMAGE_DIR, WHITE_IMAGE_DIR, connect_readonly  # noqa: E402
from models import ChatHistoryResponse, ChatRequest, ChatResponse, HistoryMessage  # noqa: E402

logger = logging.getLogger("campus_customs")



def _warm_image_cache() -> None:
    """Make the white-background copies in the background (about 20 s, once per machine)."""
    for source in sorted(IMAGE_DIR.glob("*.jpg")):
        try:
            images.white_version(source, WHITE_IMAGE_DIR)
        except Exception:
            logger.exception("Could not prepare %s", source.name)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    threading.Thread(target=_warm_image_cache, name="warm-image-cache", daemon=True).start()
    yield


app = FastAPI(title="Campus Customs API", lifespan=lifespan)
app.include_router(auth.router)

# Fields the product pages use. Search tags and the full color list stay on the server.
SUMMARY_FIELDS = ["product_id", "name", "garment_type", "category", "description", "main_color", "price", "image_url", "total_stock"]


def summary(p: dict) -> dict:
    """A product as the Products page needs it, including its filter values."""
    return {
        **{field: p[field] for field in SUMMARY_FIELDS},
        "short_description": p["short_description"],
        "collection": catalogue.collection_of(p),
        "color_family": catalogue.color_family(p["main_color"]),
        "sizes_in_stock": [s["size"] for s in p["sizes"] if s["in_stock"]],
    }


@app.get("/api/health")
def health() -> dict:
    with connect_readonly() as conn:
        count = conn.execute("SELECT COUNT(*) FROM catalogue").fetchone()[0]
    return {"status": "ok", "products": count, "chat_configured": bool(os.getenv("PORTKEY_API_KEY"))}


@app.get("/api/products")
def list_products() -> list[dict]:
    return [summary(p) for p in catalogue.all_products()]


@app.get("/api/products/browse")
def browse_products(
    q: str = Query("", max_length=100),
    category: str | None = None,
    collection: str | None = None,
    color: str | None = None,
    size: str | None = None,
    price_min: float | None = Query(None, ge=0),
    price_max: float | None = Query(None, ge=0),
    sort: str = "featured",
) -> dict:
    """The Products page: filter by category, collection (who it's for), body color, size in
    stock and price, with counts per option. The chat's "See all N" links use the same filters.
    Unknown filter values are ignored and reported back in `applied`."""
    applied = {
        "q": q.strip() or None,
        "category": category if category in catalogue.CATEGORY_SLUGS else None,
        "collection": collection if collection in (*catalogue.COLLECTIONS, catalogue.CLASSICS[0]) else None,
        "color": color if color in catalogue.COLOR_LABELS else None,
        "size": catalogue.normalize_size(size) if size else None,
        "price_min": price_min,
        "price_max": price_max,
        "sort": sort if sort in ("featured", "price_low", "price_high", "name") else "featured",
    }
    found = catalogue.browse(
        applied["q"] or "", applied["category"], applied["collection"], applied["color"],
        applied["size"], price_min, price_max, applied["sort"],
    )
    return {
        "items": [summary(p) for p in found["items"]],
        "total": found["total"],
        "facets": found["facets"],
        "applied": applied,
        "labels": {
            "category": catalogue.CATEGORY_SLUGS,
            "collection": {**{k: v[0] for k, v in catalogue.COLLECTIONS.items()}, catalogue.CLASSICS[0]: catalogue.CLASSICS[1]},
            "color": catalogue.COLOR_LABELS,
            "price": {slug: label for slug, label, _, _ in catalogue.PRICE_BUCKETS},
        },
        "price_buckets": [{"slug": s, "label": l, "min": lo, "max": hi} for s, l, lo, hi in catalogue.PRICE_BUCKETS],
    }


@app.get("/api/products/{product_id}")
def get_product(product_id: str) -> dict:
    product = catalogue.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return {**{field: product[field] for field in SUMMARY_FIELDS}, "sizes": product["sizes"]}


@app.get("/api/products/{product_id}/related")
def related_products(product_id: str) -> list[dict]:
    """Up to 4 products in the same (then a similar) design — e.g. the crewneck of a hoodie's
    design — shown under "Also in this design" on the product page."""
    base = catalogue.get_product(product_id)
    if base is None:
        raise HTTPException(status_code=404, detail="Product not found")
    ranked = []
    for p in catalogue.all_products():
        if p["product_id"] == product_id:
            continue
        match = catalogue.design_match(base, p)
        if match != "different":
            ranked.append((match != "same", p["total_stock"] == 0, p["name"], p))
    ranked.sort(key=lambda r: r[:3])
    return [summary(r[3]) for r in ranked[:4]]


@app.get("/api/chat/history")
def chat_history_route(request: Request) -> ChatHistoryResponse:
    """The logged-in customer's saved conversation, oldest first, to reload the chat panel.

    Cards are rebuilt from today's database by product_id. Guests get an empty list.
    """
    user = auth.current_user(request)
    if user is None:
        return ChatHistoryResponse(logged_in=False, messages=[])
    stored = chat_history.load_messages(user["id"], chat_history.PANEL_HISTORY_MESSAGES)
    return ChatHistoryResponse(
        logged_in=True,
        messages=[
            HistoryMessage(
                role=m["role"],
                content=chat_history.plain_text(m["content"]),
                products=agent.to_cards(chat_history.product_ids_of(m["products_json"]))[:6],
                created_at=m["created_at"],
            )
            for m in stored
            if m["role"] in ("user", "assistant")
        ],
    )


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request) -> ChatResponse:
    """One chat turn: the shopper's message (plus earlier turns) in, the agent's reply out.

    The session cookie tells the agent whether, and as whom, the shopper is logged in.
    """
    user = auth.current_user(request)
    try:
        return await agent.run_chat(body, user)
    except agent.ChatUnavailable as exc:
        raise HTTPException(503, str(exc))
    except TimeoutError:
        raise HTTPException(504, "That took too long. Please try asking again.")
    except UsageLimitExceeded:
        raise HTTPException(502, "I got tangled up on that one. Could you ask it a different way?")
    except Exception:
        logger.exception("Chat turn failed")
        raise HTTPException(502, "The shop assistant hit a snag. Please try again in a moment.")


_IMAGE_FILES = {path.name for path in IMAGE_DIR.glob("*.jpg")}


@app.get("/media/products/{filename}")
def product_image(filename: str) -> FileResponse:
    """A product photo with a white background (see images.py). Only catalogue photos are
    served; if whitening fails for any reason, the original photo is sent instead."""
    if filename not in _IMAGE_FILES:
        raise HTTPException(404, "Image not found")
    source = IMAGE_DIR / filename
    try:
        path = images.white_version(source, WHITE_IMAGE_DIR)
    except Exception:
        logger.exception("White background failed for %s; serving the original", filename)
        path = source
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("BACKEND_PORT", "8000")))
