import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchBrowse, type BrowseResult } from '../api'
import { BULLDOG_COATS } from '../bulldog'
import ProductCard from '../components/ProductCard'
import YH_Bulldog from '../components/YH_Bulldog'

// Every filter lives in the page URL (/products?category=hoodies&size=L), so a filtered view
// can be bookmarked, shared, or opened from the chat's "See all N" button. The backend
// (GET /api/products/browse) does the filtering and the counts.
const CATEGORY_ORDER = ['t-shirts', 'long-sleeve', 'crewnecks', 'hoodies', 'full-zip-hoodies', 'quarter-zips', 'jackets']
const COLLECTION_ORDER = ['family', 'colleges', 'schools', 'sports', 'classics']
const COLOR_ORDER = ['navy', 'gray', 'cream-white', 'coral']
const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
const SWATCHES: Record<string, string> = { navy: '#1f2f56', gray: '#b9bec7', 'cream-white': '#f3ead9', coral: '#e8907a' }
const SORTS: [string, string][] = [
  ['featured', 'Featured'],
  ['price_low', 'Price: low to high'],
  ['price_high', 'Price: high to low'],
  ['name', 'Name: A to Z'],
]
const NO_MIN = 0
const NO_MAX = 10000

type Loaded = { key: string; data?: BrowseResult; error?: string }

export default function Products() {
  const [params, setParams] = useSearchParams()
  const key = params.toString()
  const [loaded, setLoaded] = useState<Loaded>()
  const [filtersOpen, setFiltersOpen] = useState(false)
  const tabsRef = useRef<HTMLDivElement>(null)
  const indicatorRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    let cancelled = false
    fetchBrowse(new URLSearchParams(key))
      .then((data) => !cancelled && setLoaded({ key, data }))
      .catch(() => !cancelled && setLoaded({ key, error: "We couldn't load the catalogue. Make sure the backend is running." }))
    return () => {
      cancelled = true
    }
  }, [key])

  // While the next filter loads, keep showing the previous results (dimmed) instead of a blank page.
  const data = loaded?.data
  const loading = loaded?.key !== key

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params)
    for (const [name, value] of Object.entries(changes)) {
      if (value === null || value === '') next.delete(name)
      else next.set(name, value)
    }
    setParams(next)
  }
  const toggle = (name: string, value: string) => update({ [name]: params.get(name) === value ? null : value })
  const clearAll = () => setParams(params.get('sort') ? new URLSearchParams({ sort: params.get('sort')! }) : new URLSearchParams())

  const priceMin = params.get('price_min') ? Number(params.get('price_min')) : NO_MIN
  const priceMax = params.get('price_max') ? Number(params.get('price_max')) : NO_MAX
  const bucketFor = (min: number, max: number) => ({ price_min: min > NO_MIN ? String(min) : null, price_max: max < NO_MAX ? String(max) : null })
  const activeBucket = data?.price_buckets.find((b) => b.min === priceMin && b.max === priceMax)?.slug

  const labels = data?.labels
  const facets = data?.facets
  const count = (facet: keyof NonNullable<typeof facets>, value: string) => facets?.[facet]?.[value] ?? 0
  const categoryTotal = facets ? Object.values(facets.category).reduce((a, b) => a + b, 0) : 0
  const collectionTotal = facets ? Object.values(facets.collection).reduce((a, b) => a + b, 0) : 0

  // Removable chips for every active filter, including ones a chat link set (e.g. "Up to $70").
  const chips: { label: string; remove: () => void }[] = []
  if (params.get('q')) chips.push({ label: `“${params.get('q')}”`, remove: () => update({ q: null }) })
  for (const name of ['category', 'collection', 'color'] as const) {
    const value = params.get(name)
    if (value && labels?.[name]?.[value]) chips.push({ label: labels[name][value], remove: () => update({ [name]: null }) })
  }
  if (params.get('size')) chips.push({ label: `Size ${params.get('size')} in stock`, remove: () => update({ size: null }) })
  if (priceMin > NO_MIN || priceMax < NO_MAX) {
    const label = activeBucket
      ? labels!.price[activeBucket]
      : priceMin > NO_MIN && priceMax < NO_MAX
        ? `$${priceMin} – $${priceMax}`
        : priceMin > NO_MIN
          ? `From $${priceMin}`
          : `Up to $${priceMax}`
    chips.push({ label, remove: () => update({ price_min: null, price_max: null }) })
  }

  const size = params.get('size')

  // Sliding underline under the active category tab (moved directly, no re-render).
  const activeCategory = params.get('category') ?? ''
  useLayoutEffect(() => {
    const place = () => {
      const tab = tabsRef.current?.querySelector<HTMLButtonElement>(`button[data-slug="${activeCategory}"]`)
      const bar = indicatorRef.current
      if (!tab || !bar) return
      bar.style.width = `${tab.offsetWidth}px`
      bar.style.transform = `translateX(${tab.offsetLeft}px)`
    }
    place()
    window.addEventListener('resize', place)
    return () => window.removeEventListener('resize', place)
  }, [activeCategory, data])

  return (
    <>
      <section className="page-hero products-hero">
        <div className="products-hero-text">
          <p className="eyebrow">Products</p>
          <h1>The full lineup</h1>
          <p className="page-hero-sub">Filter by what it is, who it's for, your size, and your budget.</p>
        </div>
        <YH_Bulldog furColor={BULLDOG_COATS.cream} size={104} className="products-hero-dog" />
      </section>

      <nav className="shop-tabs" aria-label="Shop by item">
        <div className="shop-tabs-inner" ref={tabsRef}>
          <span className="tab-indicator" ref={indicatorRef} aria-hidden="true" />
          <button data-slug="" className={!params.get('category') ? 'active' : ''} onClick={() => update({ category: null })}>
            All <span>{categoryTotal}</span>
          </button>
          {CATEGORY_ORDER.map((slug) => (
            <button
              key={slug}
              data-slug={slug}
              className={params.get('category') === slug ? 'active' : ''}
              onClick={() => toggle('category', slug)}
              disabled={count('category', slug) === 0 && params.get('category') !== slug}
            >
              {labels?.category[slug] ?? slug} <span>{count('category', slug)}</span>
            </button>
          ))}
        </div>
      </nav>

      <section className="shop">
        <div className="collection-row" role="group" aria-label="Shop by who it's for">
          <span className="collection-row-label">Shop for</span>
          <button className={`pill ${!params.get('collection') ? 'active' : ''}`} onClick={() => update({ collection: null })}>
            Everyone ({collectionTotal})
          </button>
          {COLLECTION_ORDER.map((slug) => (
            <button
              key={slug}
              className={`pill ${params.get('collection') === slug ? 'active' : ''}`}
              onClick={() => toggle('collection', slug)}
              disabled={count('collection', slug) === 0 && params.get('collection') !== slug}
            >
              {labels?.collection[slug] ?? slug} ({count('collection', slug)})
            </button>
          ))}
        </div>

        <div className="shop-layout">
          <aside className={`filters ${filtersOpen ? 'open' : ''}`} aria-label="Filters">
            <div className="filter-group">
              <h2>Price</h2>
              {data?.price_buckets.map((b) => (
                <button
                  key={b.slug}
                  className={`filter-option ${activeBucket === b.slug ? 'active' : ''}`}
                  onClick={() => update(activeBucket === b.slug ? bucketFor(NO_MIN, NO_MAX) : bucketFor(b.min, b.max))}
                  disabled={count('price', b.slug) === 0 && activeBucket !== b.slug}
                >
                  <span>{b.label}</span>
                  <span className="filter-count">{count('price', b.slug)}</span>
                </button>
              ))}
            </div>

            <div className="filter-group">
              <h2>Color</h2>
              {COLOR_ORDER.map((slug) => (
                <button
                  key={slug}
                  className={`filter-option ${params.get('color') === slug ? 'active' : ''}`}
                  onClick={() => toggle('color', slug)}
                  disabled={count('color', slug) === 0 && params.get('color') !== slug}
                >
                  <span className="swatch-label">
                    <span className="swatch" style={{ background: SWATCHES[slug] }} />
                    {labels?.color[slug] ?? slug}
                  </span>
                  <span className="filter-count">{count('color', slug)}</span>
                </button>
              ))}
            </div>

            <div className="filter-group">
              <h2>My size is in stock</h2>
              <div className="size-filter">
                {SIZES.map((s) => (
                  <button
                    key={s}
                    className={size === s ? 'active' : ''}
                    onClick={() => toggle('size', s)}
                    disabled={count('size', s) === 0 && size !== s}
                    title={`${count('size', s)} products have ${s} in stock`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {chips.length > 0 && (
              <button className="text-link clear-filters" onClick={clearAll}>
                Clear all filters
              </button>
            )}
          </aside>

          <div className="shop-results">
            <div className="shop-toolbar">
              <button className="filters-toggle" onClick={() => setFiltersOpen((open) => !open)} aria-expanded={filtersOpen}>
                {filtersOpen ? 'Hide filters' : 'Filters'}
                {chips.length > 0 && ` (${chips.length})`}
              </button>
              <SearchBox key={params.get('q') ?? ''} initial={params.get('q') ?? ''} onSearch={(q) => update({ q })} />
              <label className="sort">
                <span>Sort</span>
                <select value={params.get('sort') ?? 'featured'} onChange={(e) => update({ sort: e.target.value === 'featured' ? null : e.target.value })}>
                  {SORTS.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="results-line">
              {data && (
                <p className="result-count">
                  {data.total} {data.total === 1 ? 'piece' : 'pieces'}
                  {loading && ' · updating…'}
                </p>
              )}
              {chips.map((chip) => (
                <button key={chip.label} className="active-chip" onClick={chip.remove} aria-label={`Remove filter ${chip.label}`}>
                  {chip.label} <span aria-hidden="true">×</span>
                </button>
              ))}
            </div>

            {loaded?.error && <p className="status status-error">{loaded.error}</p>}
            {!data && !loaded?.error && <p className="status">Loading products…</p>}

            {data && data.total === 0 && (
              <div className="empty-state">
                <YH_Bulldog furColor={BULLDOG_COATS.gray} size={120} />
                <h2>Handsome Dan sniffed around, but nothing matches all of that.</h2>
                <p>Try removing a filter, or ask the chat in the corner.</p>
                <button className="btn btn-blue" onClick={clearAll}>
                  Clear all filters
                </button>
              </div>
            )}

            {data && data.total > 0 && (
              <div className={`product-grid ${loading ? 'is-loading' : ''}`}>
                {data.items.map((product) => (
                  <ProductCard
                    key={product.product_id}
                    product={product}
                    note={size ? `${size} in stock` : product.total_stock === 0 ? 'Sold out' : undefined}
                    sizesInStock={product.sizes_in_stock}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </section>
    </>
  )
}

/** Search box that updates the URL 300 ms after the shopper stops typing. */
function SearchBox({ initial, onSearch }: { initial: string; onSearch: (q: string) => void }) {
  const [text, setText] = useState(initial)

  useEffect(() => {
    if (text.trim() === initial.trim()) return
    const timer = window.setTimeout(() => onSearch(text.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [text, initial, onSearch])

  return (
    <input
      className="shop-search"
      type="search"
      value={text}
      onChange={(e) => setText(e.target.value)}
      placeholder="Search: Saybrook, bulldog, dad…"
      aria-label="Search products"
      maxLength={100}
    />
  )
}
