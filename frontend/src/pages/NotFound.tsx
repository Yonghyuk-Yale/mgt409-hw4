import { Link } from 'react-router-dom'
import { BULLDOG_COATS } from '../bulldog'
import YH_Bulldog from '../components/YH_Bulldog'

export default function NotFound() {
  return (
    <section className="page-hero page-hero-short">
      <YH_Bulldog furColor={BULLDOG_COATS.gray} size={110} className="hero-dog-center" />
      <p className="eyebrow">404</p>
      <h1>Wrong turn off Broadway.</h1>
      <p className="page-hero-sub">That page doesn't exist. Handsome Dan checked twice.</p>
      <Link to="/" className="btn btn-light">
        Back home
      </Link>
    </section>
  )
}
