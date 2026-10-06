"""Tools the Campus Customs chat agent can call.

Every tool reads the real database (data/campus_customs.db) through catalogue.py, read-only,
at the moment it is called, and returns a typed result from models.py. The model only learns
facts through these tools:

    search_products          which products match what the shopper said      → product ids
    get_product_description  what one product is and looks like              ← catalogue.description, colors
    get_price                what one or more products cost                  ← catalogue.price
    check_stock              how many are left, per size or for one size     ← inventory.quantity
    catalogue_overview       the shape of the whole catalogue
    get_customer_profile     who the logged-in shopper is                    ← users (via ChatDeps)
    get_page_context         which page / product the shopper has open       ← ChatDeps.page + catalogue
    find_color_variants      "is this in pink?" — same design, other colors  ← catalogue.name, colors[0]
    make_browse_link         "See all N" link to the filtered Products page  ← catalogue.browse (same as the page)
    find_in_stock_alternatives  sold out in my size → similar items in stock  ← inventory.quantity + design match

Each tool also writes the prices and quantities it returned into ctx.deps, so the agent's
final message can be checked against what the database actually said (see agent.py).

The docstrings are sent to the model as tool descriptions, so they say when to use each tool.
"""

import re
from typing import Literal

from pydantic_ai import RunContext

import catalogue
from models import (
    LOW_STOCK_THRESHOLD,
    AlternativeOption,
    AlternativesResult,
    BrowseLink,
    CatalogueOverview,
    CategorySlug,
    CategorySummary,
    ChatDeps,
    CollectionSlug,
    ColorSlug,
    ColorVariantResult,
    CustomerInfo,
    PageInfo,
    PriceCheck,
    PriceQuote,
    ProductDescription,
    ProductMatch,
    ProductNotFound,
    SearchResult,
    SizeNotOffered,
    SizeStock,
    StockCheck,
    VariantOption,
)


def _record(ctx: RunContext[ChatDeps], tool: str, prices=(), quantities=(), products=()) -> None:
    ctx.deps.tools_used.append(tool)
    ctx.deps.products_seen.update(products)
    ctx.deps.prices_seen.update(float(p) for p in prices)
    ctx.deps.quantities_seen.update(int(q) for q in quantities)


def _not_found(ref: str, suggestions: list[dict]) -> ProductNotFound:
    return ProductNotFound(
        not_found=ref,
        did_you_mean=[{"product_id": p["product_id"], "name": p["name"]} for p in suggestions],
    )


def _status(quantity: int) -> str:
    if quantity <= 0:
        return "sold_out"
    return "low_stock" if quantity <= LOW_STOCK_THRESHOLD else "in_stock"


# =========================================================================================
# Agent-only catalogue logic. Product data and the rules the website shares with the agent
# (names, categories, search, browse filters, design matching) stay in catalogue.py; these
# helpers are used only by the tools below, so they live here with them.
# =========================================================================================

# ---------- agent-only matching: "is this in pink?" ----------
# Every product has one colorway, so "this in pink" means: another product with the same
# design whose body color is pink. Colors are matched by family on the body color
# (colors[0]); a neighbouring shade counts as "close", never as an exact match.

COLOR_FAMILIES: dict[str, tuple[list[str], list[str]]] = {
    # requested color: (exact words, close words)
    "pink": (["pink", "rose", "blush", "fuchsia", "magenta"], ["coral", "salmon"]),
    "red": (["red", "crimson", "maroon", "burgundy", "cardinal"], ["coral"]),
    "orange": (["orange"], ["coral", "salmon"]),
    "coral": (["coral"], ["pink", "salmon", "orange"]),
    "navy": (["navy"], ["blue"]),
    "blue": (["blue", "navy", "royal"], []),
    "light blue": (["light blue", "sky"], ["blue"]),
    "gray": (["gray", "grey", "charcoal", "heather"], ["silver"]),
    "charcoal": (["charcoal"], ["gray", "grey", "black"]),
    "black": (["black"], ["charcoal"]),
    "white": (["white"], ["ivory", "cream"]),
    "cream": (["cream", "ivory"], ["white"]),
    "green": (["green", "olive", "forest"], []),
    "yellow": (["yellow", "gold"], []),
    "gold": (["gold", "yellow"], []),
    "purple": (["purple", "violet", "lavender"], []),
    "brown": (["brown", "tan", "khaki"], []),
}


def color_match(requested: str, body_color: str | None) -> str:
    """'exact', 'close' or 'no' for a garment body color against the requested color."""
    if not body_color:
        return "no"
    requested = requested.strip().lower().replace("grey", "gray")
    body = body_color.lower()
    exact, close = COLOR_FAMILIES.get(requested, ([requested], []))
    if any(word in body for word in exact):
        return "exact"
    if any(word in body for word in close):
        return "close"
    return "no"


CATEGORY_SINGULAR = {
    "T-Shirts": "T-shirt",
    "Long-Sleeve Shirts": "long-sleeve shirt",
    "Crewnecks & Sweatshirts": "crewneck",
    "Hoodies": "hoodie",
    "Full-Zip Hoodies": "full-zip hoodie",
    "Quarter-Zips": "quarter-zip",
    "Jackets": "jacket",
}


# ---------- agent-only matching: "sold out in my size" alternatives ----------

def in_stock_alternatives(base: dict, size: str, limit: int = 6) -> list[dict]:
    """Products that have `size` in stock, closest to `base` first.

    Order: same design (e.g. the crewneck of the same hoodie design), similar design, same
    category in the same color family, then same category. Ties go to the closest price.
    """
    family = catalogue.color_family(base["main_color"])
    ranked = []
    for p in catalogue.all_products():
        if p["product_id"] == base["product_id"]:
            continue
        quantity = next((s["quantity"] for s in p["sizes"] if s["size"] == size), 0)
        if quantity <= 0:
            continue
        design = catalogue.design_match(base, p)
        same_category = p["category"] == base["category"]
        same_color = family is not None and catalogue.color_family(p["main_color"]) == family
        kind = CATEGORY_SINGULAR.get(p["category"], "style")
        if design == "same":
            tier, why = 0, f"same design, as a {kind}"
        elif design == "similar":
            tier, why = 1, f"similar design ({kind})"
        elif same_category and same_color:
            tier, why = 2, f"another {kind} in {catalogue.COLOR_LABELS.get(family, 'the same color').lower()}"
        elif same_category:
            tier, why = 3, f"another {kind}"
        else:
            continue
        ranked.append((tier, abs(p["price"] - base["price"]), p["name"], {**p, "quantity_in_size": quantity, "why": why}))
    ranked.sort(key=lambda r: r[:3])
    return [r[3] for r in ranked[:limit]]


# ---------- find ----------

def search_products(
    ctx: RunContext[ChatDeps],
    query: str = "",
    category: str | None = None,
    color: str | None = None,
    max_price: float | None = None,
    size_in_stock: str | None = None,
    limit: int = 8,
    sort_by: Literal["relevance", "price_low", "price_high"] = "relevance",
) -> SearchResult:
    """Find products in the Campus Customs catalogue. Start here to turn the shopper's words
    into product ids.

    Use it for any "do you have…" question: a garment type, a design, a residential college
    or school, a sport, a family member ("dad"), a color, a budget, or a size. Results include
    each product's price and whether it has any stock at all; for stock in a specific size,
    call check_stock.

    Args:
        query: The shopper's words, e.g. "navy hoodie", "bulldog", "Saybrook", "gift for my dad".
            Leave empty to list everything that passes the filters.
        category: Optional exact category. One of: T-Shirts, Long-Sleeve Shirts,
            Crewnecks & Sweatshirts, Hoodies, Full-Zip Hoodies, Quarter-Zips, Jackets.
            Only use it when the shopper names a garment type. Materials and features
            ("fleece", "tri-blend", "left chest") cut across categories: put them in query.
        color: Optional color that must appear on the garment, e.g. "gray".
        max_price: Optional price ceiling in US dollars.
        size_in_stock: Optional size (XS, S, M, L, XL, XXL, or words like "medium") that must
            currently be in stock. Only for browsing ("any hoodies in XL?"). When the shopper
            names a specific product, search without it and then call check_stock with the size.
        limit: Maximum products to return (1-12).
        sort_by: "relevance" (default), or "price_low" / "price_high" for questions like
            "what's your cheapest fleece?". If total_matches is larger than showing, there
            are more matches than were returned.
    """
    limit = max(1, min(limit, 12))
    found = catalogue.search(query, category, color, max_price, size_in_stock, limit, sort_by)
    products = found["results"]
    _record(
        ctx,
        "search_products",
        prices=[p["price"] for p in products],
        products=[p["product_id"] for p in products] + [p["product_id"] for p in found["filtered_out"]],
    )
    filters = {
        key: value
        for key, value in {
            "category": category,
            "color": color,
            "max_price": max_price,
            "size_in_stock": size_in_stock,
        }.items()
        if value not in (None, "")
    }
    return SearchResult(
        query=query,
        filters=filters,
        total_matches=found["total_matches"],
        showing=len(products),
        matched_all_terms=found["matched_all_terms"],
        unmatched_terms=found["unmatched_terms"],
        filtered_out=found["filtered_out"],
        products=[
            ProductMatch(
                product_id=p["product_id"],
                name=p["name"],
                category=p["category"],
                price=p["price"],
                main_color=p["main_color"],
                in_stock=p["total_stock"] > 0,
            )
            for p in products
        ],
    )


# ---------- 1) description ----------

def get_product_description(ctx: RunContext[ChatDeps], product: str) -> ProductDescription | ProductNotFound:
    """Read one product's description and colors from the database.

    Use this whenever the shopper asks what a product looks like, what is printed on it, what
    color it is, or what kind of garment it is. Describe only what this returns.

    Args:
        product: A product_id from search_products (preferred) or the product's name.
    """
    found, suggestions = catalogue.resolve_product(product)
    _record(ctx, "get_product_description", products=[found["product_id"]] if found else [])
    if found is None:
        return _not_found(product, suggestions)
    return _description(found)


def _description(found: dict) -> ProductDescription:
    return ProductDescription(
        product_id=found["product_id"],
        name=found["name"],
        category=found["category"],
        garment_type=found["garment_type"],
        description=found["description"],
        description_available=found["has_description"],
        main_color=found["main_color"],
        other_colors=found["colors"][1:],
    )


# ---------- 2) price ----------

def get_price(ctx: RunContext[ChatDeps], products: list[str]) -> PriceCheck:
    """Read the current price of one or more products from the database.

    Call this before stating or comparing a specific product's price. Prices are in US dollars.

    Args:
        products: One or more product_ids from search_products (preferred) or product names,
            e.g. ["basic-hoodie-big-yale"] or ["yale-dad-hoodie", "yale-mom-hoodie"].
    """
    quotes, missing = [], []
    for ref in products[:12]:
        found, suggestions = catalogue.resolve_product(ref)
        if found is None:
            missing.append(_not_found(ref, suggestions))
        else:
            quotes.append(PriceQuote(product_id=found["product_id"], name=found["name"], price=found["price"]))
    _record(ctx, "get_price", prices=[q.price for q in quotes], products=[q.product_id for q in quotes])
    return PriceCheck(quotes=quotes, not_found=missing)


# ---------- 3) stock ----------

def check_stock(
    ctx: RunContext[ChatDeps], product: str, size: str | None = None
) -> StockCheck | SizeNotOffered | ProductNotFound:
    """Read live stock for one product from the inventory table: units left in each size.

    Call this before saying a product or size is available, how many are left, or that it is
    sold out. A quantity of 0 means sold out in that size.

    Args:
        product: A product_id from search_products (preferred) or the product's name.
        size: Optional size the shopper asked about: XS, S, M, L, XL, XXL, or words such as
            "medium", "extra large", "2XL". Leave empty to get every size.
    """
    found, suggestions = catalogue.resolve_product(product)
    if found is None:
        _record(ctx, "check_stock")
        return _not_found(product, suggestions)

    sizes = [SizeStock(size=s["size"], quantity=s["quantity"], status=_status(s["quantity"])) for s in found["sizes"]]
    _record(
        ctx,
        "check_stock",
        quantities=[s.quantity for s in sizes] + [found["total_stock"]],
        products=[found["product_id"]],
    )

    requested = None
    if size:
        requested = catalogue.normalize_size(size)
        if requested is None or requested not in {s.size for s in sizes}:
            return SizeNotOffered(
                product_id=found["product_id"],
                name=found["name"],
                requested_size=size,
                sizes_offered=[s.size for s in sizes],
            )
    match = next((s for s in sizes if s.size == requested), None)
    return StockCheck(
        product_id=found["product_id"],
        name=found["name"],
        requested_size=requested,
        requested_size_quantity=match.quantity if match else None,
        requested_size_status=match.status if match else None,
        sizes=sizes,
        sizes_in_stock=[s.size for s in sizes if s.quantity > 0],
        sold_out_sizes=[s.size for s in sizes if s.quantity <= 0],
        total_stock=found["total_stock"],
    )


# ---------- overview ----------

def catalogue_overview(ctx: RunContext[ChatDeps]) -> CatalogueOverview:
    """Summarize the whole catalogue: categories, how many products each has, their prices,
    and the sizes we offer. Use this for broad questions like "what do you sell?" or
    "what's your price range?".
    """
    products = catalogue.all_products()
    summaries = []
    for category in catalogue.CATEGORIES:
        group = [p for p in products if p["category"] == category]
        if group:
            summaries.append(
                CategorySummary(
                    category=category,
                    product_count=len(group),
                    prices=sorted({p["price"] for p in group}),
                    in_stock_count=sum(1 for p in group if p["total_stock"] > 0),
                )
            )
    _record(ctx, "catalogue_overview", prices=[p for s in summaries for p in s.prices])
    return CatalogueOverview(
        total_products=len(products),
        sizes_offered=catalogue.SIZE_ORDER,
        categories=summaries,
    )


# ---------- the customer and the page they are on ----------

def get_customer_profile(ctx: RunContext[ChatDeps]) -> CustomerInfo:
    """Who you are talking to: the logged-in customer's first name, last name, email, member-since
    date and how many chat messages are saved for them. Returns logged_in=false for a guest.

    Use it when the shopper asks who they are logged in as, whether you remember them, or
    anything about their own account. Never reveal anything about other customers.
    """
    _record(ctx, "get_customer_profile")
    customer = ctx.deps.customer
    return CustomerInfo(logged_in=customer is not None, profile=customer, chat_is_saved=customer is not None)


def get_page_context(ctx: RunContext[ChatDeps]) -> PageInfo:
    """What the shopper has on screen right now: the page path and, on a product page, that
    product's full description, colors and price (from the database).

    Use it whenever the shopper says "this", "it", "this one", "this hoodie" without naming a
    product, or asks about "the one I'm looking at".
    """
    page = ctx.deps.page
    found = catalogue.get_product(page.product_id) if page and page.product_id else None
    _record(
        ctx,
        "get_page_context",
        prices=[found["price"]] if found else [],
        products=[found["product_id"]] if found else [],
    )
    return PageInfo(
        path=page.path if page else None,
        page_type=page.page_type if page else None,
        viewing_product=_description(found) if found else None,
        price=found["price"] if found else None,
    )


def find_color_variants(
    ctx: RunContext[ChatDeps], color: str, product: str | None = None
) -> ColorVariantResult | ProductNotFound | str:
    """Answer "do you have this in <color>?". Every product comes in one colorway, so this looks
    for OTHER products with the same (or a similar) design whose body color is the requested
    color, and lists the same-design products in every color we have.

    Args:
        color: The color the shopper asked for, e.g. "pink", "gray", "black".
        product: The product to start from (product_id or name). Leave empty to use the
            product on the page the shopper is viewing.
    """
    ref = product or (ctx.deps.page.product_id if ctx.deps.page else None)
    if not ref:
        _record(ctx, "find_color_variants")
        return "No product given and the shopper is not on a product page. Ask which product they mean."
    base, suggestions = catalogue.resolve_product(ref)
    if base is None:
        _record(ctx, "find_color_variants")
        return _not_found(ref, suggestions)

    def option(p: dict, design: str) -> VariantOption:
        return VariantOption(
            product_id=p["product_id"],
            name=p["name"],
            category=p["category"],
            main_color=p["main_color"],
            price=p["price"],
            in_stock=p["total_stock"] > 0,
            design_match=design,
            color_match=color_match(color, p["main_color"]),
        )

    others = [p for p in catalogue.all_products() if p["product_id"] != base["product_id"]]
    related = [option(p, catalogue.design_match(base, p)) for p in others]
    same_design = sorted(
        (o for o in related if o.design_match != "different"), key=lambda o: o.design_match != "same"
    )
    in_color_any = sorted(
        (o for o in related if o.design_match == "different" and o.color_match != "no"),
        key=lambda o: o.color_match != "exact",
    )[:5]
    shown = same_design + in_color_any
    _record(
        ctx,
        "find_color_variants",
        prices=[base["price"]] + [o.price for o in shown],
        products=[base["product_id"]] + [o.product_id for o in shown],
    )
    return ColorVariantResult(
        base_product_id=base["product_id"],
        base_name=base["name"],
        base_main_color=base["main_color"],
        requested_color=color,
        base_already_in_color=color_match(color, base["main_color"]) == "exact",
        same_design=same_design,
        requested_color_same_design=[o for o in same_design if o.color_match != "no"],
        requested_color_any_design=in_color_any,
        body_colors_we_carry=sorted({p["main_color"] for p in catalogue.all_products() if p["main_color"]}),
    )


TOOLS = [
    search_products,
    get_product_description,
    get_price,
    check_stock,
    catalogue_overview,
    get_customer_profile,
    get_page_context,
    find_color_variants,
]


# ---------- Problem 9: browse links and sold-out alternatives ----------

def make_browse_link(
    ctx: RunContext[ChatDeps],
    query: str = "",
    category: CategorySlug | None = None,
    collection: CollectionSlug | None = None,
    color: ColorSlug | None = None,
    size_in_stock: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
) -> BrowseLink | str:
    """Make a link to the Products page with these filters, and count what it will show.

    Use it when there are more matching products than the 6 cards you can show (e.g. "what
    hoodies do you have?" -> 25), or when the shopper wants to browse. Put the returned `url` in
    `browse_url`; the chat shows it as a "See all N" button. Quote the returned `count`.

    Args:
        query: Free-text words, only if no filter below expresses them (e.g. "bulldog").
        category: t-shirts, long-sleeve, crewnecks, hoodies, full-zip-hoodies, quarter-zips, jackets.
        collection: family (Mom/Dad/…), colleges (residential colleges), schools (graduate &
            professional schools), sports, classics.
        color: Body color family: navy, gray, cream-white, coral.
        size_in_stock: Only products with this size in stock (XS–XXL or words like "medium").
        min_price / max_price: Price range in US dollars.
    """
    size = catalogue.normalize_size(size_in_stock) if size_in_stock else None
    if size_in_stock and size is None:
        return f"'{size_in_stock}' is not a size we make. Sizes: XS, S, M, L, XL, XXL."
    found = catalogue.browse(query, category, collection, color, size, min_price, max_price)
    url = catalogue.browse_url(
        q=query.strip() or None, category=category, collection=collection, color=color,
        size=size, price_min=min_price, price_max=max_price,
    )
    words = [catalogue.COLOR_LABELS[color].lower()] if color else []
    words.append(catalogue.CATEGORY_SLUGS[category].lower() if category else "products")
    if collection:
        words.append(f"from {catalogue.collection_label(collection)}")
    if query.strip():
        words.append(f"matching \"{query.strip()}\"")
    if size:
        words.append(f"in {size}")
    if max_price is not None:
        words.append(f"up to ${max_price:g}")
    if min_price is not None:
        words.append(f"from ${min_price:g}")
    link = BrowseLink(url=url, count=found["total"], label=f"See all {found['total']} " + " ".join(words))
    ctx.deps.browse_links[url] = link
    _record(ctx, "make_browse_link", quantities=[found["total"]])
    return link


def find_in_stock_alternatives(ctx: RunContext[ChatDeps], product: str, size: str) -> AlternativesResult | ProductNotFound | str:
    """When a product is sold out in the shopper's size, find similar products that DO have
    that size in stock: same design in another garment first, then similar designs, then the
    same kind of garment in the same color.

    Call it right after check_stock reports sold_out for the size the shopper wants, and offer
    the top 2–3 with their `why`.

    Args:
        product: product_id (preferred) or name of the sold-out product.
        size: The shopper's size: XS, S, M, L, XL, XXL, or words like "medium".
    """
    found, suggestions = catalogue.resolve_product(product)
    if found is None:
        _record(ctx, "find_in_stock_alternatives")
        return _not_found(product, suggestions)
    code = catalogue.normalize_size(size)
    if code is None:
        _record(ctx, "find_in_stock_alternatives")
        return f"'{size}' is not a size we make. Sizes: XS, S, M, L, XL, XXL."
    alternatives = in_stock_alternatives(found, code)
    own = next((s["quantity"] for s in found["sizes"] if s["size"] == code), 0)
    _record(
        ctx,
        "find_in_stock_alternatives",
        prices=[found["price"]] + [a["price"] for a in alternatives],
        quantities=[own] + [a["quantity_in_size"] for a in alternatives],
        products=[found["product_id"]] + [a["product_id"] for a in alternatives],
    )
    return AlternativesResult(
        product_id=found["product_id"],
        name=found["name"],
        size=code,
        quantity_in_size=own,
        alternatives=[
            AlternativeOption(
                product_id=a["product_id"],
                name=a["name"],
                category=a["category"],
                main_color=a["main_color"],
                price=a["price"],
                quantity_in_size=a["quantity_in_size"],
                why=a["why"],
            )
            for a in alternatives
        ],
    )


TOOLS += [make_browse_link, find_in_stock_alternatives]
