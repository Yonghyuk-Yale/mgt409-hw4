import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type { SignupInput } from '../api'
import { useAuth } from '../auth-context'

const EMPTY: SignupInput = {
  first_name: '',
  last_name: '',
  email: '',
  password: '',
  confirm_password: '',
}

// Quick checks in the browser for instant feedback. The server repeats every check
// (and more), so these are a convenience, not the security boundary.
function checkForm(form: SignupInput): string | null {
  if (!form.first_name.trim() || !form.last_name.trim()) return 'Please enter your first and last name.'
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim())) return 'Please enter a valid email address.'
  if (form.password.length < 8) return 'Password must be at least 8 characters.'
  if (form.password !== form.confirm_password) return 'Passwords do not match.'
  return null
}

export default function CreateAccount() {
  const { user, signup } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState<SignupInput>(EMPTY)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const update = (field: keyof SignupInput) => (event: ChangeEvent<HTMLInputElement>) =>
    setForm((current) => ({ ...current, [field]: event.target.value }))

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const problem = checkForm(form)
    if (problem) {
      setError(problem)
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      await signup(form)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-up failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (user) {
    return (
      <section className="auth-page">
        <div className="auth-card">
          <p className="eyebrow eyebrow-blue">Create account</p>
          <h1>You're on the roster, {user.first_name}.</h1>
          <p className="auth-lead">Logged in as {user.email}.</p>
          <Link to="/products" className="btn btn-blue auth-submit">
            Browse products
          </Link>
        </div>
      </section>
    )
  }

  const mismatch = form.confirm_password.length > 0 && form.password !== form.confirm_password

  return (
    <section className="auth-page">
      <form className="auth-card" onSubmit={submit} noValidate>
        <p className="eyebrow eyebrow-blue">Create account</p>
        <h1>Join the roster.</h1>
        <p className="auth-lead">One account for the shop and the chat.</p>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        <div className="field-row">
          <label className="field">
            <span>First name</span>
            <input autoComplete="given-name" value={form.first_name} onChange={update('first_name')} maxLength={50} />
          </label>
          <label className="field">
            <span>Last name</span>
            <input autoComplete="family-name" value={form.last_name} onChange={update('last_name')} maxLength={50} />
          </label>
        </div>
        <label className="field">
          <span>Email</span>
          <input type="email" autoComplete="email" value={form.email} onChange={update('email')} maxLength={254} />
        </label>
        <label className="field">
          <span>Password</span>
          <input
            type="password"
            autoComplete="new-password"
            value={form.password}
            onChange={update('password')}
            maxLength={128}
          />
          <small>At least 8 characters. Very common passwords are not allowed.</small>
        </label>
        <label className="field">
          <span>Confirm password</span>
          <input
            type="password"
            autoComplete="new-password"
            value={form.confirm_password}
            onChange={update('confirm_password')}
            maxLength={128}
            aria-invalid={mismatch}
          />
          {mismatch && <small className="field-warning">Passwords don't match yet.</small>}
        </label>

        <button className="btn btn-blue auth-submit" disabled={submitting}>
          {submitting ? 'Creating account…' : 'Create account'}
        </button>
        <p className="auth-switch">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </section>
  )
}
