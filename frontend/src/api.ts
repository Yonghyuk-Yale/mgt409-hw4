// Types and fetch helpers for the FastAPI backend (backend/main.py).

export interface ProductSummary {
  product_id: string
  name: string
  garment_type: string
  description: string
  main_color: string | null
  price: number
  image_url: string
  total_stock: number
}

/** A product as listed on the Products page (GET /api/products/browse). */
export interface ListedProduct extends ProductSummary {
  category: string
  short_description: string
  collection: string
  color_family: string | null
  sizes_in_stock: string[]
}

export type FacetName = 'category' | 'collection' | 'color' | 'size' | 'price'

export interface BrowseResult {
  items: ListedProduct[]
  total: number
  facets: Record<FacetName, Record<string, number>>
  applied: {
    q: string | null
    category: string | null
    collection: string | null
    color: string | null
    size: string | null
    price_min: number | null
    price_max: number | null
    sort: string
  }
  labels: Record<'category' | 'collection' | 'color' | 'price', Record<string, string>>
  price_buckets: { slug: string; label: string; min: number; max: number }[]
}

/** Other products in the same (or a similar) design, for "Also in this design". */
export const fetchRelated = (productId: string) =>
  getJson<ListedProduct[]>(`/api/products/${encodeURIComponent(productId)}/related`)

/** Ask the chat assistant a question from anywhere on the site (opens the chat panel). */
export const askDan = (question: string) =>
  window.dispatchEvent(new CustomEvent<string>('ask-dan', { detail: question }))

/** The Products page's filters, passed straight through from the page URL. */
export const fetchBrowse = (search: URLSearchParams) =>
  getJson<BrowseResult>(`/api/products/browse?${search.toString()}`)

export interface SizeStock {
  size: string
  quantity: number
  in_stock: boolean
}

export interface ProductDetail extends ProductSummary {
  sizes: SizeStock[]
}

export class NotFoundError extends Error {}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (response.status === 404) throw new NotFoundError('Not found')
  if (!response.ok) throw new Error(`Request failed (${response.status})`)
  return response.json() as Promise<T>
}

export const fetchProducts = () => getJson<ListedProduct[]>('/api/products')

export const fetchProduct = (productId: string) =>
  getJson<ProductDetail>(`/api/products/${encodeURIComponent(productId)}`)

// ---------- accounts ----------

export interface User {
  id: number
  first_name: string
  last_name: string
  name: string
  email: string
}

export interface SignupInput {
  first_name: string
  last_name: string
  email: string
  password: string
  confirm_password: string
}

/** POST JSON; the session lives in an HttpOnly cookie, so nothing is stored in JS. */
async function postJson<T>(url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data?.detail
    if (typeof detail === 'string') throw new Error(detail)
    throw new Error(
      response.status >= 500
        ? "The shop server isn't responding right now. Please try again in a moment."
        : 'Please check the form and try again.',
    )
  }
  return data as T
}

export async function fetchMe(): Promise<User | null> {
  const response = await fetch('/api/auth/me')
  return response.ok ? ((await response.json()) as User | null) : null
}

export const login = (email: string, password: string) =>
  postJson<User>('/api/auth/login', { email, password })

export const signup = (input: SignupInput) => postJson<User>('/api/auth/signup', input)

export const logout = () => postJson<{ ok: boolean }>('/api/auth/logout')

// ---------- chat ----------

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

/** A matched product under a chat answer. The server builds it from the database; the
 *  agent only chooses which product_ids to show. Mirrors ProductCard in backend/models.py. */
export interface ProductCardData {
  product_id: string
  name: string
  price: number
  image_url: string
  short_description: string
  main_color: string | null
  total_stock: number
  sizes_in_stock: string[]
  url: string // the product's own page, /products/<product_id>
}

/** "See all N" link to the filtered Products page, made by the agent's make_browse_link. */
export interface BrowseLink {
  url: string
  count: number
  label: string
}

export interface ChatReply {
  message: string
  products: ProductCardData[]
  tools_used: string[]
  browse: BrowseLink | null
}

export type PageType = 'home' | 'products' | 'product' | 'about' | 'login' | 'create-account' | 'other'

/** The page the shopper has open, sent with every chat message (mirrors PageContext). */
export interface PageContext {
  path: string
  page_type: PageType
  product_id: string | null
}

export function pageContextFor(pathname: string): PageContext {
  const product = pathname.match(/^\/products\/([^/]+)\/?$/)
  if (product) return { path: pathname, page_type: 'product', product_id: decodeURIComponent(product[1]) }
  const types: Record<string, PageType> = {
    '/': 'home',
    '/products': 'products',
    '/about': 'about',
    '/login': 'login',
    '/create-account': 'create-account',
  }
  return { path: pathname, page_type: types[pathname] ?? 'other', product_id: null }
}

/** One chat turn. The session cookie tells the agent who is logged in; `history` is only
 *  used for guests (a logged-in customer's history is loaded from the database). */
export const sendChat = (message: string, history: ChatTurn[], page: PageContext) =>
  postJson<ChatReply & { saved: boolean }>('/api/chat', { message, history, page })

export interface HistoryMessage extends ChatTurn {
  products: ProductCardData[]
  created_at: string
}

/** The logged-in customer's saved conversation (empty for guests). */
export async function fetchChatHistory(): Promise<HistoryMessage[]> {
  const response = await fetch('/api/chat/history')
  if (!response.ok) return []
  const data = (await response.json()) as { logged_in: boolean; messages: HistoryMessage[] }
  return data.messages
}

export const formatPrice = (price: number) =>
  price.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
