import { Link } from 'react-router-dom'
import { BULLDOG_COATS } from '../bulldog'
import YH_Bulldog from './YH_Bulldog'

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <YH_Bulldog furColor={BULLDOG_COATS.white} size={48} />
          <div>
            <p className="footer-title">Campus Customs</p>
            <p>57 Broadway, New Haven, CT</p>
            <p>Printing on Broadway since 1975.</p>
          </div>
        </div>
        <nav className="footer-links">
          <Link to="/">Home</Link>
          <Link to="/products">Products</Link>
          <Link to="/about">About Us</Link>
          <Link to="/login">Log in</Link>
          <Link to="/create-account">Create account</Link>
        </nav>
      </div>
      <p className="footer-note">
        Built as a course project for MGT 409 at the Yale School of Management. Not the official
        Campus Customs online store. Bulldog illustration adapted from the MGT 409 course materials.
      </p>
    </footer>
  )
}
