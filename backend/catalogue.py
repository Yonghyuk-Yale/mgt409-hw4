"""Catalogue data layer shared by the website routes (main.py) and the agent tools (tools.py).

Everything here reads the database read-only. The database itself is never cleaned up;
display names, garment categories and search synonyms are applied in code (Problem 2).
Keeping one copy of these rules means the chatbot quotes exactly the names, prices and
stock the product pages show.
"""

import json
import re
import sqlite3
from functools import lru_cache

from db import connect_readonly
from images import CACHE_VERSION as IMAGE_VERSION

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

# ---------- display names ----------

NAME_OVERRIDES = {
    "ua-mens-tech-l-s-2-0": "UA Men's Tech L/S 2.0",
    "ua-gameday-double-knit-hood": "UA Gameday Double Knit Hood",
    "champion-reverse-weave-hoodie-1": "Champion Reverse Weave Hoodie",
    "champion-mens-triumph-raglan-crew": "Champion Men's Triumph Raglan Crew",
    "yale-sports-creqneck-field-hockey": "Yale Sports Crewneck Field Hockey",
    # Photo and description show a crewneck / quarter-zip, not what the slug says.
    "squash-left-chest-tennis": "Squash Left Chest Crewneck",
    "school-of-architecture-crewneck": "School of Architecture 1/4-Zip",
    "t-felt-y-heavyweight": "Felt Y Heavyweight T-Shirt",
    "2025-yale-vs-harvard-t-shirt": "2025 Yale vs. Harvard T-Shirt",
    "district-vit-crewneck-vintage-bulldog": "District VIT Crewneck Vintage Bulldog",
    "district-vit-crewneck-vintage-standing-bulldog": "District VIT Crewneck Vintage Standing Bulldog",
    "district-vit-hoodie-vintage-bulldog": "District VIT Hoodie Vintage Bulldog",
    "district-vit-hoodie-vintage-sailor-bulldog": "District VIT Hoodie Vintage Sailor Bulldog",
}

NAME_REPLACEMENTS = [
    (r"\bT Shirt\b", "T-Shirt"),
    (r"\b1 4 Zip\b", "1/4-Zip"),
    (r"\bTri Blend\b", "Tri-Blend"),
    (r"\bTrack Field\b", "Track & Field"),
    (r"\bFull Zip\b", "Full-Zip"),
    (r"\bOf\b", "of"),
    (r"\bAnd\b", "and"),
]

# Three rows were never described (the vision step was blocked when the data was built).
STUB_MARKER = "Vision blocked"
STUB_DESCRIPTION = "Full product description coming soon. The photo shows the exact design."


def display_name(product_id: str, raw_name: str) -> str:
    if product_id in NAME_OVERRIDES:
        return NAME_OVERRIDES[product_id]
    name = raw_name
    for pattern, replacement in NAME_REPLACEMENTS:
        name = re.sub(pattern, replacement, name)
    return name[0].upper() + name[1:]


def has_description(description: str) -> bool:
    return STUB_MARKER not in description


def clean_description(description: str) -> str:
    return description if has_description(description) else STUB_DESCRIPTION


SHORT_DESCRIPTION_CHARS = 90


def short_description(description: str) -> str:
    """One-line summary for product cards: the description cut at a word boundary."""
    if not has_description(description):
        return "Description coming soon. See the photo for the design."
    text = description.strip()
    if len(text) <= SHORT_DESCRIPTION_CHARS:
        return text
    cut = text[:SHORT_DESCRIPTION_CHARS].rsplit(" ", 1)[0].rstrip(",;:-— ")
    return cut + "…"


# ---------- garment categories ----------
# garment_type is free text with 22 spellings; these 7 groups are what shoppers ask for.
# Order matters: the first matching rule wins.

CATEGORY_RULES = [
    ("quarter-zip", "Quarter-Zips"),
    ("full-zip hooded", "Full-Zip Hoodies"),
    ("jacket", "Jackets"),
    ("performance shirt", "Long-Sleeve Shirts"),
    ("t-shirt", "T-Shirts"),
    ("hood", "Hoodies"),
    ("crew", "Crewnecks & Sweatshirts"),
    ("mockneck", "Crewnecks & Sweatshirts"),
]
CATEGORIES = [
    "T-Shirts",
    "Long-Sleeve Shirts",
    "Crewnecks & Sweatshirts",
    "Hoodies",
    "Full-Zip Hoodies",
    "Quarter-Zips",
    "Jackets",
]


def category_of(garment_type: str) -> str:
    lowered = garment_type.lower()
    for needle, category in CATEGORY_RULES:
        if needle in lowered:
            return category
    return "Other"


# ---------- rows ----------

def _inventory(conn: sqlite3.Connection, product_id: str) -> dict[str, int]:
    return dict(conn.execute("SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)))


def _record(row: sqlite3.Row, stock: dict[str, int]) -> dict:
    colors = json.loads(row["colors"])
    return {
        "product_id": row["product_id"],
        "name": display_name(row["product_id"], row["name"]),
        "garment_type": row["garment_type"],
        "category": category_of(row["garment_type"]),
        "description": clean_description(row["description"]),
        "short_description": short_description(row["description"]),
        "has_description": has_description(row["description"]),
        # First color is the garment body; the rest are lettering/graphic colors.
        "main_color": colors[0] if colors else None,
        "colors": colors,
        "search_tags": json.loads(row["search_tags"]),
        "price": row["price"],
        # The version makes browsers fetch the white-background photo instead of reusing an
        # older copy cached under the same address (bumped whenever images.py changes).
        "image_url": f"/media/{row['image_file_path']}?v={IMAGE_VERSION}",
        "sizes": [
            {"size": size, "quantity": stock[size], "in_stock": stock[size] > 0}
            for size in SIZE_ORDER
            if size in stock
        ],
        "total_stock": sum(stock.values()),
    }


def all_products() -> list[dict]:
    """Every product with stock, sorted by display name. Read fresh each call."""
    with connect_readonly() as conn:
        rows = conn.execute("SELECT * FROM catalogue").fetchall()
        stock: dict[str, dict[str, int]] = {}
        for product_id, size, quantity in conn.execute("SELECT product_id, size, quantity FROM inventory"):
            stock.setdefault(product_id, {})[size] = quantity
    records = [_record(row, stock.get(row["product_id"], {})) for row in rows]
    return sorted(records, key=lambda record: record["name"])


def get_product(product_id: str) -> dict | None:
    with connect_readonly() as conn:
        row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if row is None:
            return None
        return _record(row, _inventory(conn, product_id))


def get_products(product_ids: list[str]) -> list[dict]:
    """Look up several products, keeping the given order and dropping unknown ids."""
    found = [get_product(product_id) for product_id in dict.fromkeys(product_ids)]
    return [product for product in found if product]


def resolve_product(ref: str) -> tuple[dict | None, list[dict]]:
    """Find a product from a product_id or a (display or raw) product name.

    Returns (product, []) on an exact match, or (None, up to 3 closest products) otherwise,
    so the agent can ask "did you mean…?" instead of guessing.
    """
    ref = ref.strip()
    product = get_product(ref) or get_product(ref.lower().replace(" ", "-"))
    if product:
        return product, []
    wanted = re.sub(r"[^a-z0-9]+", " ", ref.lower()).strip()
    for candidate in all_products():
        if re.sub(r"[^a-z0-9]+", " ", candidate["name"].lower()).strip() == wanted:
            return candidate, []
    return None, search(ref, limit=3)["results"]


_SIZE_WORDS = {
    "XS": ["xs", "x-small", "x small", "xsmall", "extra small", "extra-small"],
    "S": ["s", "small", "sm"],
    "M": ["m", "medium", "med", "md"],
    "L": ["l", "large", "lg"],
    "XL": ["xl", "x-large", "x large", "xlarge", "extra large", "extra-large"],
    "XXL": ["xxl", "2xl", "xx-large", "xx large", "xxlarge", "2x", "extra extra large", "double xl"],
}
_SIZE_LOOKUP = {word: code for code, words in _SIZE_WORDS.items() for word in words}


def normalize_size(text: str) -> str | None:
    """'medium' -> 'M', '2XL' -> 'XXL'. None if it isn't a size we know."""
    return _SIZE_LOOKUP.get(re.sub(r"\s+", " ", text.strip().lower()))


# ---------- search ----------
# Shoppers rarely use the catalogue's exact words, so text and query are normalized the
# same way and a few synonyms are expanded (e.g. "Handsome Dan" is Yale's bulldog).

_PHRASES = [
    (r"\bt[\s-]?shirts?\b", " tshirt "),
    (r"(?:\bquarter|\b1/4|\b1 4)[\s-]?zips?\b", " quarterzip "),
    (r"\bfull[\s-]?zips?\b", " fullzip "),
    (r"\bcrew[\s-]?necks?\b", " crewneck "),
    (r"\blong[\s-]?sleeves?\b", " longsleeve "),
    (r"\bshort[\s-]?sleeves?\b", " shortsleeve "),
    (r"\bhandsome\s+dan\b", " bulldog "),
    (r"\btrack\s*(?:&|and)\s*field\b", " trackfield "),
    (r"\bgrey\b", " gray "),
]
_SYNONYMS = {
    "tee": ["tshirt"],
    "hood": ["hoodie"],
    "hooded": ["hoodie"],
    "hoody": ["hoodie"],
    "sweatshirt": ["sweatshirt", "crewneck", "hoodie"],
    "crew": ["crewneck"],
    "jumper": ["crewneck"],
    "sweater": ["crewneck", "fleece"],
    "coat": ["jacket"],
    "mascot": ["bulldog"],
    "dog": ["bulldog"],
    "bulldogs": ["bulldog"],
    "parent": ["mom", "dad"],
    "mother": ["mom"],
    "father": ["dad"],
    "grandmother": ["grandma"],
    "grandfather": ["grandpa"],
    "family": ["mom", "dad", "grandma", "grandpa", "aunt", "uncle", "brother", "cousin"],
}
_STOPWORDS = set(
    "a an the any anything some something do does you your have has got get with on in of for to "
    "me my i im i'm is are it its this that these those and or show find looking look want need "
    "what which who item items thing things stuff u ur please can could would like yale campus "
    "customs merch gear apparel".split()
)


def _normalize(text: str) -> str:
    text = text.lower()
    for pattern, replacement in _PHRASES:
        text = re.sub(pattern, replacement, text)
    return text


def _words(text: str) -> set[str]:
    words = set()
    for word in re.findall(r"[a-z0-9']+", _normalize(text)):
        words.add(word)
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            words.add(word[:-1])
    return words


def query_terms(query: str) -> list[str]:
    terms: list[str] = []
    for word in re.findall(r"[a-z0-9']+", _normalize(query)):
        if word in _STOPWORDS:
            continue
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        terms.extend(_SYNONYMS.get(word, [word]))
    return list(dict.fromkeys(terms))


@lru_cache(maxsize=1)
def _search_index() -> dict[str, dict[str, set[str]]]:
    """Words per field per product. Text never changes at run time (stock is read live)."""
    with connect_readonly() as conn:
        rows = conn.execute("SELECT * FROM catalogue").fetchall()
    index = {}
    for row in rows:
        index[row["product_id"]] = {
            "name": _words(display_name(row["product_id"], row["name"]) + " " + row["product_id"].replace("-", " ")),
            "type": _words(row["garment_type"] + " " + category_of(row["garment_type"])),
            "tags": _words(" ".join(json.loads(row["search_tags"]))),
            # Body color outranks lettering/graphic colors: "navy hoodie" means a navy hoodie.
            "main_color": _words(json.loads(row["colors"])[0]) if json.loads(row["colors"]) else set(),
            "colors": _words(" ".join(json.loads(row["colors"])[1:])),
            "description": _words(row["description"]) if has_description(row["description"]) else set(),
        }
    return index


_FIELD_WEIGHTS = {"name": 3.0, "main_color": 3.0, "type": 2.5, "tags": 2.0, "colors": 1.0, "description": 1.0}


def search(
    query: str = "",
    category: str | None = None,
    color: str | None = None,
    max_price: float | None = None,
    size: str | None = None,
    limit: int = 8,
    sort_by: str = "relevance",
) -> dict:
    """Rank products for a free-text query plus optional filters.

    Only the best tier is returned: products matching the most query words. Words that
    matched no product at all (e.g. "pink") are reported so the agent can say plainly that
    we don't carry them. With no query, every product passing the filters matches,
    cheapest first.

    "We don't carry it" and "it didn't pass your filters" are kept apart: unmatched_terms
    is judged against the whole catalogue, and strong text matches that a filter removed
    come back in filtered_out with the reason (e.g. sold out in the requested size).
    """
    terms = query_terms(query)
    index = _search_index()
    size = (normalize_size(size) or size.upper()) if size else None
    seen_terms: set[str] = set()
    scored, rejected = [], []
    for product in all_products():
        fields = index[product["product_id"]]
        score, matched = 0.0, 0
        for term in terms:
            best = max((w for f, w in _FIELD_WEIGHTS.items() if term in fields[f]), default=0.0)
            if best:
                score += best
                matched += 1
                seen_terms.add(term)
        if terms and matched == 0:
            continue
        reason = None
        if category and product["category"].lower() != category.lower():
            reason = f"not in category {category}"
        elif max_price is not None and product["price"] > max_price:
            reason = f"costs more than ${max_price:g}"
        elif color and not any(color.lower() in c.lower() for c in product["colors"]):
            reason = f"has no {color}"
        elif size and not any(s["size"] == size and s["in_stock"] for s in product["sizes"]):
            reason = f"sold out in {size}"
        item = (matched, score, -product["price"], product)
        if reason:
            rejected.append((item, reason))
        else:
            scored.append(item)
    # Products that matched the query at least as well as anything returned, but were
    # removed by a filter: the shopper's exact item may be among them.
    best_kept = max((item[0] for item in scored), default=0)
    best_rejected = max((item[0] for item, _ in rejected), default=0)
    filtered_out = []
    if terms and best_rejected and best_rejected >= best_kept:
        for item, reason in sorted(rejected, key=lambda r: r[0][1], reverse=True):
            if item[0] == best_rejected:
                filtered_out.append({"product_id": item[3]["product_id"], "name": item[3]["name"], "reason": reason})
        filtered_out = filtered_out[:3]
    top = max((item[0] for item in scored), default=0)
    if terms and scored:
        scored = [item for item in scored if item[0] == top]
        scored.sort(key=lambda item: item[1], reverse=True)
    else:
        scored.sort(key=lambda item: item[2], reverse=True)
    # Stable sorts: equal prices keep their relevance order.
    if sort_by == "price_low":
        scored.sort(key=lambda item: item[3]["price"])
    elif sort_by == "price_high":
        scored.sort(key=lambda item: item[3]["price"], reverse=True)
    return {
        "results": [item[3] for item in scored[:limit]],
        "total_matches": len(scored),
        # False means no single product matched every word (e.g. "mom tee": we have mom
        # crewnecks and plain tees, but no mom tee).
        "matched_all_terms": bool(scored) and top == len(terms),
        "unmatched_terms": [term for term in terms if term not in seen_terms],
        "filtered_out": filtered_out,
    }


# ---------- design matching (shared: the product page's "Also in this design" and the agent) ----------
# Two products share a design when their names differ only in garment and color words,
# e.g. Yale Mom Hoodie and Yale Mom Crewneck.

_COLOR_WORDS = {
    "black", "blue", "blush", "brown", "burgundy", "cardinal", "charcoal", "coral", "cream", "crimson", "dark", "dusty", "forest", "fuchsia", "gold", "gray", "green", "grey", "heather", "ivory", "khaki", "lavender", "light", "light blue", "magenta", "maroon", "multicolor", "navy", "olive", "orange", "pink", "purple", "red", "rose", "royal", "salmon", "silver", "sky", "tan", "tri", "violet", "white", "yellow",
}
_GARMENT_WORDS = {
    "tshirt", "t", "shirt", "tee", "crewneck", "crew", "hoodie", "hood", "hooded", "quarterzip", "zip",
    "fleece", "jacket", "sweater", "sweatshirt", "mockneck", "fullzip", "longsleeve", "long", "sleeve",
    "pullover", "1", "4", "heavyweight", "blend",
}


def design_words(product: dict) -> set[str]:
    """Words that describe the design, from the product name minus garment and color words."""
    return {w for w in _words(product["name"]) if w not in _GARMENT_WORDS and w not in _COLOR_WORDS and len(w) > 1}


def design_match(base: dict, other: dict) -> str:
    """'same' if the names differ only in garment/color words, 'similar' if they overlap a lot."""
    a, b = design_words(base), design_words(other)
    if not a or not b:
        return "different"
    if a == b:
        return "same"
    overlap = len(a & b) / len(a | b)
    return "similar" if overlap >= 0.5 else "different"


# ---------- browsing: categories, collections, filters (Products page and chat links) ----------
# One implementation serves both the Products page filters and the agent's "See all N" link,
# so the number the chat promises is the number the page shows.

CATEGORY_SLUGS = {
    "t-shirts": "T-Shirts",
    "long-sleeve": "Long-Sleeve Shirts",
    "crewnecks": "Crewnecks & Sweatshirts",
    "hoodies": "Hoodies",
    "full-zip-hoodies": "Full-Zip Hoodies",
    "quarter-zips": "Quarter-Zips",
    "jackets": "Jackets",
}

# Who a product is for, from its name. First matching rule wins; anything else is a Yale classic.
COLLECTIONS = {
    "family": ("Family", r"\b(mom|dad|grandma|grandpa|aunt|uncle|brother|cousin|sister)\b"),
    "colleges": (
        "Residential Colleges",
        r"\b(benjamin franklin|berkeley|branford|davenport|ezra stiles|grace hopper|jonathan edwards|"
        r"morse|pauli murray|pierson|saybrook|silliman|timothy dwight|trumbull)\b",
    ),
    "schools": (
        "Graduate & Professional Schools",
        r"\b(school of|law school|divinity|forest school)\b",
    ),
    "sports": (
        "Sports",
        r"\b(baseball|basketball|football|hockey|soccer|tennis|golf|volleyball|lacrosse|fencing|sailing|"
        r"squash|diving|swimming|crew|track|the game|bowl|harvard)\b",
    ),
}
CLASSICS = ("classics", "Yale Classics")

COLOR_FAMILY_RULES = [  # body color (colors[0]) -> filter swatch; first match wins
    ("navy", "navy"),
    ("blue", "navy"),
    ("gray", "gray"),
    ("grey", "gray"),
    ("charcoal", "gray"),
    ("cream", "cream-white"),
    ("ivory", "cream-white"),
    ("white", "cream-white"),
    ("coral", "coral"),
]
COLOR_LABELS = {"navy": "Navy", "gray": "Gray", "cream-white": "Cream & White", "coral": "Coral"}
PRICE_BUCKETS = [  # (slug, label, min, max), inclusive
    ("under-40", "Under $40", 0.0, 39.99),
    ("40-60", "$40 – $60", 40.0, 60.0),
    ("60-80", "$60 – $80", 60.01, 80.0),
    ("80-up", "$80 & up", 80.01, 10_000.0),
]


def collection_of(product: dict) -> str:
    text = f"{product['name']} {product['product_id'].replace('-', ' ')}".lower()
    for slug, (_, pattern) in COLLECTIONS.items():
        if re.search(pattern, text):
            return slug
    return CLASSICS[0]


def collection_label(slug: str) -> str:
    return COLLECTIONS[slug][0] if slug in COLLECTIONS else CLASSICS[1]


def color_family(main_color: str | None) -> str | None:
    if not main_color:
        return None
    lowered = main_color.lower()
    return next((slug for needle, slug in COLOR_FAMILY_RULES if needle in lowered), None)


def category_slug(category: str) -> str | None:
    return next((slug for slug, label in CATEGORY_SLUGS.items() if label == category), None)


def browse(
    q: str = "",
    category: str | None = None,
    collection: str | None = None,
    color: str | None = None,
    size: str | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    sort: str = "featured",
) -> dict:
    """Filter the catalogue the way the Products page does.

    Filters are slugs (CATEGORY_SLUGS, COLLECTIONS, COLOR_LABELS). `size` keeps only products
    with that size in stock. Facet counts say, for each option, how many products would match
    if that option were picked while every other filter stays as it is.
    """
    q = (q or "").strip()
    size = normalize_size(size) if size else None
    pool = search(q, limit=1000)["results"] if q else all_products()
    rank = {p["product_id"]: i for i, p in enumerate(pool)}

    def keep(p: dict, skip: str | None = None) -> bool:
        if skip != "category" and category and category_slug(p["category"]) != category:
            return False
        if skip != "collection" and collection and collection_of(p) != collection:
            return False
        if skip != "color" and color and color_family(p["main_color"]) != color:
            return False
        if skip != "size" and size and not any(s["size"] == size and s["in_stock"] for s in p["sizes"]):
            return False
        if skip != "price" and price_min is not None and p["price"] < price_min:
            return False
        if skip != "price" and price_max is not None and p["price"] > price_max:
            return False
        return True

    items = [p for p in pool if keep(p)]
    if sort == "price_low":
        items.sort(key=lambda p: (p["price"], p["name"]))
    elif sort == "price_high":
        items.sort(key=lambda p: (-p["price"], p["name"]))
    elif sort == "name":
        items.sort(key=lambda p: p["name"])
    elif q:  # featured with a search: best match first
        items.sort(key=lambda p: rank[p["product_id"]])
    else:  # featured: in-stock first, then by name
        items.sort(key=lambda p: (p["total_stock"] == 0, p["name"]))

    def facet(dimension: str, values_of) -> dict[str, int]:
        counts: dict[str, int] = {}
        for p in pool:
            if keep(p, skip=dimension):
                for value in values_of(p):
                    if value:
                        counts[value] = counts.get(value, 0) + 1
        return counts

    facets = {
        "category": facet("category", lambda p: [category_slug(p["category"])]),
        "collection": facet("collection", lambda p: [collection_of(p)]),
        "color": facet("color", lambda p: [color_family(p["main_color"])]),
        "size": facet("size", lambda p: [s["size"] for s in p["sizes"] if s["in_stock"]]),
        "price": facet("price", lambda p: [slug for slug, _, lo, hi in PRICE_BUCKETS if lo <= p["price"] <= hi]),
    }
    return {"items": items, "total": len(items), "facets": facets}


def browse_url(**filters) -> str:
    """Website URL of the Products page with these filters (empty values left out)."""
    from urllib.parse import urlencode

    params = {
        key: (f"{value:g}" if isinstance(value, float) else value)
        for key, value in filters.items()
        if value not in (None, "", "featured")
    }
    return "/products" + (f"?{urlencode(params)}" if params else "")
