import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth-context'

const MAIN_LINKS = [
  { to: '/', label: 'Home', end: true },
  { to: '/products', label: 'Products', end: false },
  { to: '/about', label: 'About Us', end: false },
]

export default function NavBar() {
  const [menuOpen, setMenuOpen] = useState(false)
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const close = () => setMenuOpen(false)

  const handleLogout = async () => {
    close()
    await logout()
    navigate('/')
  }

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="logo" onClick={close}>
          <span className="logo-mark">CC</span>
          <span className="logo-text">
            Campus Customs
            <small>57 Broadway · New Haven · Est. 1975</small>
          </span>
        </Link>

        <button
          className="menu-toggle"
          aria-label="Toggle navigation"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span />
          <span />
          <span />
        </button>

        <nav className={`nav-links ${menuOpen ? 'open' : ''}`}>
          {MAIN_LINKS.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end} onClick={close}>
              {link.label}
            </NavLink>
          ))}
          <span className="nav-divider" />
          {user ? (
            <>
              <span className="nav-greeting">Hi, {user.first_name}</span>
              <button className="nav-logout" onClick={handleLogout}>
                Log out
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login" onClick={close}>
                Log in
              </NavLink>
              <NavLink to="/create-account" className="nav-cta" onClick={close}>
                Create account
              </NavLink>
            </>
          )}
        </nav>
      </div>
    </header>
  )
}
