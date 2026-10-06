import { Link } from 'react-router-dom'
import { formatPrice, type ProductSummary } from '../api'
import { useReveal } from '../useReveal'

interface Props {
  product: ProductSummary
  /** Small badge on the photo, e.g. "L in stock" when the size filter is on, or "Sold out". */
  note?: string
  /** Sizes with stock, revealed on hover so shoppers can judge before clicking. */
  sizesInStock?: string[]
}

const ALL_SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL']

export default function ProductCard({ product, note, sizesInStock }: Props) {
  // The photo is "printed" onto the card (squeegee wipe) the first time it scrolls into view.
  const { ref, visible } = useReveal<HTMLAnchorElement>()

  return (
    <Link ref={ref} to={`/products/${product.product_id}`} className={`product-card ${visible ? 'is-visible' : ''}`}>
      <div className="product-card-image">
        <img src={product.image_url} alt={product.name} loading="lazy" />
        <span className="squeegee" aria-hidden="true" />
        {note && <span className={`product-card-note ${note === 'Sold out' ? 'sold-out' : ''}`}>{note}</span>}
        {sizesInStock && (
          <span className="product-card-sizes" aria-label={`In stock: ${sizesInStock.join(', ') || 'none'}`}>
            {ALL_SIZES.map((size) => (
              <span key={size} className={sizesInStock.includes(size) ? '' : 'out'}>
                {size}
              </span>
            ))}
          </span>
        )}
      </div>
      <div className="product-card-body">
        <h3>{product.name}</h3>
        <p className="product-card-price">{formatPrice(product.price)}</p>
        <p className="product-card-desc">{product.description}</p>
      </div>
    </Link>
  )
}
