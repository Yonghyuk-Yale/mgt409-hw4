import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchBrowse, fetchProducts, type BrowseResult, type ListedProduct } from '../api'
import { BULLDOG_COATS } from '../bulldog'
import Marquee from '../components/Marquee'
import ProductCard from '../components/ProductCard'
import YH_Bulldog from '../components/YH_Bulldog'

const FEATURED_IDS = [
  'basic-hoodie-big-yale',
  'district-vit-hoodie-vintage-sailor-bulldog',
  'champion-reverse-weave-crewneck',
  'yale-bowl-t-shirt',
]

const PROMISES = [
  {
    title: 'Printed down the block',
    text: "Our print floor shares a roof with the register. Your sweatshirt didn't cross an ocean to get here. It crossed the shop.",
    coat: BULLDOG_COATS.fawn,
  },
  {
    title: 'Every kind of Bulldog',
    text: 'Residential colleges, professional schools, varsity sports, and the relatives who cheer the loudest from the stands.',
    coat: BULLDOG_COATS.cream,
  },
  {
    title: 'Straight answers',
    text: "Ask about a price or a size and you get the number from our shelves, not a guess. Sold out means sold out, and we'll say so.",
    coat: BULLDOG_COATS.gray,
  },
]

// "Shop for" tiles open the Products page with that collection filter already on.
const COLLECTION_TILES = [
  { slug: 'family', blurb: 'Mom, Dad, Grandpa & the whole cheering section', coat: BULLDOG_COATS.fawn },
  { slug: 'colleges', blurb: 'Rep your residential college', coat: BULLDOG_COATS.cream },
  { slug: 'schools', blurb: 'Law, Art, Medicine, Music & more', coat: BULLDOG_COATS.gray },
  { slug: 'sports', blurb: 'Varsity colors, game-day ready', coat: BULLDOG_COATS.white },
  { slug: 'classics', blurb: 'Big YALE, crests & bulldogs', coat: BULLDOG_COATS.fawn },
]

export default function Home() {
  const [featured, setFeatured] = useState<ListedProduct[]>([])
  const [shop, setShop] = useState<BrowseResult | null>(null)

  useEffect(() => {
    fetchProducts()
      .then((products) =>
        setFeatured(
          FEATURED_IDS.map((id) => products.find((p) => p.product_id === id)).filter(
            (p): p is ListedProduct => Boolean(p),
          ),
        ),
      )
      .catch(() => setFeatured([]))
    fetchBrowse(new URLSearchParams())
      .then(setShop)
      .catch(() => setShop(null))
  }, [])

  return (
    <>
      <section className="hero">
        <div className="hero-inner">
          <div className="hero-text">
            <p className="eyebrow">Est. 1975 · 57 Broadway, New Haven · in the old York Square Cinema</p>
            <Marquee kicker="Now printing" title="Wear the Blue" />
            <h1 className="hero-tagline">Mean it.</h1>
            <p className="hero-sub">
              Yale gear printed a stone's throw from Old Campus, by a family shop that has been pulling
              ink on Broadway for half a century.
            </p>
            <div className="hero-actions">
              <Link to="/products" className="btn btn-light">
                Shop the collection
              </Link>
              <Link to="/about" className="btn btn-outline-light">
                Read our story
              </Link>
            </div>
          </div>
          <div className="hero-mascot" aria-hidden="true">
            <YH_Bulldog furColor={BULLDOG_COATS.white} size={250} className="dan-bob" />
            <p>Handsome Dan approves.</p>
          </div>
        </div>
      </section>

      <div className="ticker" aria-hidden="true">
        <div className="ticker-track">
          {[0, 1].map((copy) => (
            <span key={copy}>
              Printed in-house on Broadway <i>★</i> 102 styles <i>★</i> XS to XXL <i>★</i> Residential colleges & schools{' '}
              <i>★</i> Straight answers on stock <i>★</i> Since 1975 <i>★</i>{' '}
            </span>
          ))}
        </div>
      </div>

      <section className="promises">
        {PROMISES.map((promise) => (
          <article key={promise.title} className="promise">
            <YH_Bulldog furColor={promise.coat} size={44} className="promise-dog" />
            <h2>{promise.title}</h2>
            <p>{promise.text}</p>
          </article>
        ))}
      </section>

      {shop && (
        <section className="section">
          <div className="section-head">
            <div>
              <p className="eyebrow eyebrow-blue">Shop for</p>
              <h2>Who are we dressing today?</h2>
            </div>
            <Link to="/products" className="text-link">
              Browse everything →
            </Link>
          </div>
          <div className="collection-tiles">
            {COLLECTION_TILES.map((tile) => (
              <Link key={tile.slug} to={`/products?collection=${tile.slug}`} className="collection-tile">
                <YH_Bulldog furColor={tile.coat} size={64} />
                <span className="collection-tile-name">{shop.labels.collection[tile.slug]}</span>
                <span className="collection-tile-blurb">{tile.blurb}</span>
                <span className="collection-tile-count">{shop.facets.collection[tile.slug] ?? 0} pieces →</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {featured.length > 0 && (
        <section className="section section-tight">
          <div className="section-head">
            <div>
              <p className="eyebrow eyebrow-blue">This week</p>
              <h2>The starting lineup</h2>
            </div>
            <Link to="/products" className="text-link">
              See all products →
            </Link>
          </div>
          <div className="product-grid">
            {featured.map((product) => (
              <ProductCard key={product.product_id} product={product} sizesInStock={product.sizes_in_stock} />
            ))}
          </div>
        </section>
      )}

      <section className="family-band">
        <div className="family-inner">
          <div className="bulldog-family" aria-hidden="true">
            <YH_Bulldog furColor={BULLDOG_COATS.gray} size={78} />
            <YH_Bulldog furColor={BULLDOG_COATS.fawn} size={96} />
            <YH_Bulldog furColor={BULLDOG_COATS.cream} size={88} />
            <YH_Bulldog furColor={BULLDOG_COATS.white} size={58} />
          </div>
          <p className="eyebrow">Not just for the Class of '30</p>
          <h2>Mom. Dad. Grandpa. Your cousin who still brings it up.</h2>
          <p>
            The family section is real, and it is popular. The people who drove you to move-in day
            deserve a sweatshirt that says so.
          </p>
          <Link to="/products?collection=family" className="btn btn-blue">
            Find theirs
          </Link>
        </div>
      </section>
    </>
  )
}
