import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth-context'

export default function Login() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Log-in failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (user) {
    return (
      <section className="auth-page">
        <div className="auth-card">
          <p className="eyebrow eyebrow-blue">Log in</p>
          <h1>You're already in, {user.first_name}.</h1>
          <p className="auth-lead">Logged in as {user.email}.</p>
          <Link to="/products" className="btn btn-blue auth-submit">
            Browse products
          </Link>
        </div>
      </section>
    )
  }

  return (
    <section className="auth-page">
      <form className="auth-card" onSubmit={submit} noValidate>
        <p className="eyebrow eyebrow-blue">Log in</p>
        <h1>Welcome back, Bulldog.</h1>
        <p className="auth-lead">Log in with the email you signed up with.</p>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        <label className="field">
          <span>Email</span>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>Password</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>

        <button className="btn btn-blue auth-submit" disabled={submitting || !email || !password}>
          {submitting ? 'Logging in…' : 'Log in'}
        </button>
        <p className="auth-switch">
          New here? <Link to="/create-account">Create an account</Link>
        </p>
      </form>
    </section>
  )
}
