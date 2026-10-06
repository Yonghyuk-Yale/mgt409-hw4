"""Structured types for the Campus Customs chat agent.

Three groups:
- Chat API types: what the website sends to POST /api/chat and what it gets back.
- Agent types: the agent's structured output (AgentReply) and its run-time context (ChatDeps).
- Tool types: what each tool in tools.py returns to the model.

The agent never writes product data itself. It returns product ids, and the server turns
them into ProductCards from the database, so a price or stock number on a card can never
be invented by the model. Numbers inside the message text are checked too (see ChatDeps).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MAX_MESSAGE_CHARS = 1000
MAX_HISTORY_TURNS = 20
MAX_CARDS = 6
LOW_STOCK_THRESHOLD = 5  # "only a few left" at or below this many units

SizeCode = Literal["XS", "S", "M", "L", "XL", "XXL"]
StockStatus = Literal["in_stock", "low_stock", "sold_out"]


# ---------- chat API ----------

class ChatTurn(BaseModel):
    """One earlier message in the conversation, as shown in the chat panel."""

    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


PageType = Literal["home", "products", "product", "about", "login", "create-account", "other"]


class PageContext(BaseModel):
    """Which page of the website the shopper had open when they sent the message.

    Sent by the chat panel with every message, so "this hoodie" can be resolved to the
    product on screen. The server re-checks product_id against the database.
    """

    path: str = Field(max_length=200, description="Website route, e.g. /products/yale-mom-hoodie")
    page_type: PageType = "other"
    product_id: str | None = Field(default=None, max_length=120)


class ChatRequest(BaseModel):
    """Body of POST /api/chat."""

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    history: list[ChatTurn] = Field(
        default_factory=list,
        max_length=MAX_HISTORY_TURNS,
        description="Earlier turns, used for guests only. Logged-in history comes from the database.",
    )
    page: PageContext | None = None


class ProductCard(BaseModel):
    """A product shown under a chat answer. Built by the server from the database at the
    moment of the answer — the agent supplies only the product_id."""

    product_id: str
    name: str
    price: float
    image_url: str = Field(description="Product photo, served by the backend at /media/products/...")
    short_description: str = Field(description="One-line summary of catalogue.description.")
    main_color: str | None
    total_stock: int
    sizes_in_stock: list[str]
    url: str = Field(description="Website route of the product's own page, /products/<product_id>.")


class ChatResponse(BaseModel):
    """What POST /api/chat returns to the chat panel."""

    message: str
    products: list[ProductCard] = Field(default_factory=list)
    tools_used: list[str] = Field(
        default_factory=list,
        description="Database tools the agent called for this answer, in order (for transparency/testing).",
    )
    saved: bool = Field(
        default=False, description="True if this turn was stored in chat_messages (logged-in shoppers only)."
    )
    browse: "BrowseLink | None" = Field(
        default=None, description="A 'See all N' link to the filtered Products page, when there are more matches than cards."
    )


class HistoryMessage(BaseModel):
    """One stored message, as reloaded into the chat panel."""

    role: Literal["user", "assistant"]
    content: str
    products: list[ProductCard] = Field(default_factory=list)
    created_at: str


class ChatHistoryResponse(BaseModel):
    """What GET /api/chat/history returns. Guests always get an empty list."""

    logged_in: bool
    messages: list[HistoryMessage]


# ---------- the customer, as the agent may see them ----------

class CustomerProfile(BaseModel):
    """The only customer fields the agent ever sees. Never the password hash or user id."""

    first_name: str
    last_name: str
    email: str
    member_since: str = Field(description="Account creation date (UTC), YYYY-MM-DD.")
    saved_messages: int = Field(description="How many chat messages are stored for this customer.")


# ---------- agent ----------

class AgentReply(BaseModel):
    """The agent's structured output for every chat turn."""

    message: str = Field(
        description=(
            "The reply shown to the shopper. Plain text, no markdown. Short paragraphs; "
            "a list may use lines starting with '• '."
        )
    )
    product_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_CARDS,
        description=(
            "product_id values (exactly as returned by the tools) of the products this reply "
            "talks about, most relevant first. They are shown as cards under the message. "
            "Empty if no specific product is discussed."
        ),
    )
    browse_url: str | None = Field(
        default=None,
        description=(
            "A url returned by make_browse_link in this turn, shown as a 'See all N' button that "
            "opens the filtered Products page. Use it when there are more matches than cards."
        ),
    )


@dataclass
class ChatDeps:
    """Run-time context for one chat turn, shared by the agent, its tools and the output check.

    The tools write down every price and stock quantity they read from the database. Before a
    reply is accepted, every dollar amount and "N left" in it must appear in that ledger
    (or in the shopper's own words, e.g. a budget). Otherwise the model is told to look it up.
    """

    customer: CustomerProfile | None = None  # None for a guest who is not logged in
    page: PageContext | None = None  # the page on screen, product_id already checked against the DB
    shopper_numbers: set[float] = field(default_factory=set)  # numbers the shopper typed
    prices_seen: set[float] = field(default_factory=set)
    quantities_seen: set[int] = field(default_factory=set)
    products_seen: set[str] = field(default_factory=set)  # product_ids a tool returned this turn
    browse_links: dict[str, "BrowseLink"] = field(default_factory=dict)  # url -> link made this turn
    tools_used: list[str] = field(default_factory=list)


# ---------- tool results ----------

class ProductNotFound(BaseModel):
    """Returned when a tool is given a product that isn't in the catalogue."""

    not_found: str = Field(description="The product id or name that was asked for.")
    did_you_mean: list[dict[str, str]] = Field(
        description="Closest catalogue products as {product_id, name}. Empty means nothing close."
    )


class ProductMatch(BaseModel):
    """Compact product summary returned by search_products. Size-level stock is not included:
    use check_stock for that."""

    product_id: str
    name: str
    category: str
    price: float
    main_color: str | None
    in_stock: bool = Field(description="True if at least one size has stock.")


class SearchResult(BaseModel):
    query: str
    filters: dict[str, str | float]
    total_matches: int
    showing: int
    matched_all_terms: bool = Field(
        description="False means no single product matched every word of the query."
    )
    unmatched_terms: list[str] = Field(
        description="Query words that matched no product in the whole catalogue (e.g. a color we don't carry)."
    )
    filtered_out: list[dict[str, str]] = Field(
        default_factory=list,
        description=(
            "Products that matched the query but were removed by a filter, as "
            "{product_id, name, reason}, e.g. reason 'sold out in XS'. These products exist: "
            "never say we don't carry them."
        ),
    )
    products: list[ProductMatch]


class ProductDescription(BaseModel):
    """Returned by get_product_description: what the product is and looks like."""

    product_id: str
    name: str
    category: str
    garment_type: str
    description: str
    description_available: bool = Field(
        description="False means the catalogue has no written description for this product yet."
    )
    main_color: str | None = Field(description="Body color of the garment.")
    other_colors: list[str] = Field(
        description="Lettering/graphic colors on the same garment. Not other color options."
    )


class PriceQuote(BaseModel):
    product_id: str
    name: str
    price: float
    currency: Literal["USD"] = "USD"


class PriceCheck(BaseModel):
    """Returned by get_price."""

    quotes: list[PriceQuote]
    not_found: list[ProductNotFound] = Field(default_factory=list)


class SizeStock(BaseModel):
    size: SizeCode
    quantity: int
    status: StockStatus


class StockCheck(BaseModel):
    """Returned by check_stock: live stock for one product, per size."""

    product_id: str
    name: str
    requested_size: SizeCode | None = Field(
        description="The size the shopper asked about, normalized (e.g. 'medium' -> 'M'). None if no size was asked."
    )
    requested_size_quantity: int | None
    requested_size_status: StockStatus | None
    sizes: list[SizeStock] = Field(description="Every size we make for this product, XS to XXL.")
    sizes_in_stock: list[SizeCode]
    sold_out_sizes: list[SizeCode]
    total_stock: int
    low_stock_threshold: int = LOW_STOCK_THRESHOLD


class SizeNotOffered(BaseModel):
    """Returned by check_stock when the requested size isn't one we make."""

    product_id: str
    name: str
    requested_size: str
    sizes_offered: list[SizeCode]


class CustomerInfo(BaseModel):
    """Returned by get_customer_profile."""

    logged_in: bool
    profile: CustomerProfile | None = None
    chat_is_saved: bool = Field(description="True when this conversation is being stored for the customer.")


class PageInfo(BaseModel):
    """Returned by get_page_context: what the shopper has on screen right now."""

    path: str | None
    page_type: PageType | None
    viewing_product: ProductDescription | None = Field(
        description="The product whose page is open, or None if the shopper isn't on a product page."
    )
    price: float | None = None


class VariantOption(BaseModel):
    product_id: str
    name: str
    category: str
    main_color: str | None
    price: float
    in_stock: bool
    design_match: Literal["same", "similar", "different"] = Field(
        description="same = same design (e.g. Yale Mom crewneck vs Yale Mom hoodie); similar = shares design words."
    )
    color_match: Literal["exact", "close", "no"] = Field(
        description="How the product's body color compares with the requested color. close = a neighbouring shade."
    )


class ColorVariantResult(BaseModel):
    """Returned by find_color_variants."""

    base_product_id: str
    base_name: str
    base_main_color: str | None
    requested_color: str
    base_already_in_color: bool
    same_design: list[VariantOption] = Field(
        description="Every other product with the same or a similar design, whatever its color."
    )
    requested_color_same_design: list[VariantOption] = Field(
        description="Same/similar design AND the requested body color (exact or close). Empty = no such variant."
    )
    requested_color_any_design: list[VariantOption] = Field(
        description="Other products whose body color is the requested color (exact or close), any design."
    )
    body_colors_we_carry: list[str] = Field(description="All distinct garment body colors in the catalogue.")


class CategorySummary(BaseModel):
    category: str
    product_count: int
    prices: list[float]
    in_stock_count: int


class CatalogueOverview(BaseModel):
    total_products: int
    sizes_offered: list[str]
    categories: list[CategorySummary]


# ---------- Problem 9: browse links and sold-out alternatives ----------

CategorySlug = Literal["t-shirts", "long-sleeve", "crewnecks", "hoodies", "full-zip-hoodies", "quarter-zips", "jackets"]
CollectionSlug = Literal["family", "colleges", "schools", "sports", "classics"]
ColorSlug = Literal["navy", "gray", "cream-white", "coral"]


class BrowseLink(BaseModel):
    """A link to the Products page with filters applied, and how many products it shows."""

    url: str = Field(description="Website route, e.g. /products?category=hoodies&color=navy")
    count: int = Field(description="How many products the page will show with these filters.")
    label: str = Field(description="Button text, e.g. 'See all 11 navy hoodies'.")


class AlternativeOption(BaseModel):
    product_id: str
    name: str
    category: str
    main_color: str | None
    price: float
    quantity_in_size: int
    why: str = Field(description="Why it is suggested, e.g. 'same design, as a crewneck'.")


class AlternativesResult(BaseModel):
    """Returned by find_in_stock_alternatives."""

    product_id: str
    name: str
    size: SizeCode
    quantity_in_size: int = Field(description="Units of the original product left in this size (0 = sold out).")
    alternatives: list[AlternativeOption] = Field(
        description="Products with this size in stock, closest first. Empty = nothing comparable in this size."
    )


ChatResponse.model_rebuild()


# ---------- Problem 12: audit trail (output/audit_trail.json) ----------

StopReason = Literal["completed", "content_filter", "limit_exceeded", "timeout", "model_error", "unavailable", "error"]


class AuditToolCall(BaseModel):
    """One tool call inside a loop step. `final_result` is the agent handing in its answer;
    `ok: false` there means a server guard rejected the answer and sent it back."""

    tool: str
    args: str = Field(description="Arguments, shortened to one line.")
    result: str = Field(description="What the tool returned (or the guard's rejection), shortened.")
    ok: bool


class AuditStep(BaseModel):
    """One turn of the agent loop: a model response and the tool calls it made."""

    step: int
    at: datetime
    tool_calls: list[AuditToolCall]


class AuditEntry(BaseModel):
    """One chat turn, appended to output/audit_trail.json (never rewritten or reset).

    No customer identity is stored (the file is committed to a public repository): only
    whether the shopper was logged in, and the question with emails, long numbers and
    passwords masked.
    """

    run_id: str
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    model: str
    shopper: Literal["guest", "logged_in"]
    page: str | None
    question: str
    steps: list[AuditStep]
    step_count: int
    tool_call_count: int
    guard_rejections: int = Field(description="Answers sent back by grounded_in_database before one passed.")
    stop_reason: StopReason
    answer: str | None
    product_ids: list[str]
    browse_url: str | None
    saved_to_history: bool
    error: str | None
    usage: dict[str, int]
