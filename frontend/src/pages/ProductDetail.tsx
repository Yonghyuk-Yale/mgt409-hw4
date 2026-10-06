import { useEffect, useState, type MouseEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  askDan,
  fetchProduct,
  fetchRelated,
  formatPrice,
  NotFoundError,
  type ListedProduct,
  type ProductDetail as Product,
} from '../api'
import ProductCard from '../components/ProductCard'

const LOW_STOCK = 5

export default function ProductDetail() {
  const { productId = '' } = useParams()
  // Keyed by product id so a stale result never shows while the next product loads.
  const [result, setResult] = useState<{ id: string; product?: Product; related?: ListedProduct[]; error?: string }>()

  useEffect(() => {
    Promise.all([fetchProduct(productId), fetchRelated(productId).catch(() => [])])
      .then(([product, related]) => setResult({ id: productId, product, related }))
      .catch((err) =>
        setResult({
          id: productId,
          error:
            err instanceof NotFoundError
              ? "We don't carry a product with that name."
              : "We couldn't load this product. Make sure the backend is running.",
        }),
      )
  }, [productId])

  const current = result?.id === productId ? result : undefined
  const product = current?.product
  const error = current?.error

  // Hover zoom: the photo scales up around the pointer.
  const onZoomMove = (event: MouseEvent<HTMLDivElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    event.currentTarget.style.setProperty('--zx', `${((event.clientX - box.left) / box.width) * 100}%`)
    event.currentTarget.style.setProperty('--zy', `${((event.clientY - box.top) / box.height) * 100}%`)
  }

  const lowSizes = product?.sizes.filter((s) => s.in_stock && s.quantity <= LOW_STOCK) ?? []

  return (
    <section className="section detail-page">
      <Link to="/products" className="text-link back-link">
        ← All products
      </Link>

      {error && <p className="status status-error">{error}</p>}
      {!error && !product && <p className="status">Loading…</p>}

      {product && (
        <>
          <div className="detail">
            <div className="detail-image" onMouseMove={onZoomMove}>
              <img src={product.image_url} alt={product.name} />
              <span className="print-stamp" aria-hidden="true">
                Printed on
                <br />
                Broadway
              </span>
            </div>

            <div className="detail-info">
              <p className="eyebrow eyebrow-blue">{product.garment_type}</p>
              <h1>{product.name}</h1>
              <p className="detail-price">{formatPrice(product.price)}</p>
              <p className="detail-desc">{product.description}</p>

              <div className="sizes">
                <div className="sizes-head">
                  <h2>Sizes &amp; stock</h2>
                  <span>{product.total_stock > 0 ? `${product.total_stock} in stock` : 'Sold out'}</span>
                </div>
                <ul className="size-grid">
                  {product.sizes.map((size) => (
                    <li key={size.size} className={`size-chip ${size.in_stock ? '' : 'sold-out'}`}>
                      <span className="size-label">{size.size}</span>
                      <span className="size-qty">{size.in_stock ? `${size.quantity} left` : 'Sold out'}</span>
                    </li>
                  ))}
                </ul>
                {lowSizes.length > 0 && (
                  <p className="low-stock-note">
                    Going fast: only {lowSizes.map((s) => `${s.quantity} in ${s.size}`).join(', ')}.
                  </p>
                )}
              </div>

              <div className="ask-dan-row">
                <span>Questions? Dan checks the shelves for you.</span>
                <div className="ask-dan-buttons">
                  <button className="ask-dan-btn" onClick={() => askDan(`Is the ${product.name} in stock in my size?`)}>
                    Is my size in stock?
                  </button>
                  <button className="ask-dan-btn" onClick={() => askDan(`Does this come in other colors?`)}>
                    Other colors?
                  </button>
                </div>
              </div>
            </div>
          </div>

          {current?.related && current.related.length > 0 && (
            <div className="related">
              <div className="section-head">
                <div>
                  <p className="eyebrow eyebrow-blue">Same print, different fit</p>
                  <h2>Also in this design</h2>
                </div>
              </div>
              <div className="product-grid">
                {current.related.map((item) => (
                  <ProductCard key={item.product_id} product={item} sizesInStock={item.sizes_in_stock} />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  )
}
