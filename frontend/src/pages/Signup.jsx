import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { CheckCircle2, Loader2, AlertCircle } from 'lucide-react'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { register as apiRegister, login as apiLogin } from '../api/client'
import { useAuth } from '../context/AuthContext'

// Maintenance pass Part B — HR sign-up page. The backend register endpoint
// (POST /api/v1/auth/register) has always existed but had no UI, so HR had to
// create accounts via Swagger. is_hr is NOT a form field: the backend always
// provisions HR accounts and does not accept is_hr from the request body
// (UserCreate = email, full_name, password only) — nothing to expose here.
//
// On success we auto-login: the MVP is single-HR (see README) and the endpoint
// sets is_hr=True unconditionally, so calling /auth/login right after register
// is the simplest path into the app (vs. a separate "check your email" flow we
// don't have email delivery for in this context).

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const MIN_PASSWORD = 8

export default function Signup() {
  const navigate = useNavigate()
  const { login: loginSession } = useAuth()
  const [form, setForm] = useState({ full_name: '', email: '', password: '', confirm: '' })
  const [fieldErrors, setFieldErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  function update(field) {
    return (e) => {
      setForm((f) => ({ ...f, [field]: e.target.value }))
      // Clear this field's inline error as the user edits it.
      setFieldErrors((errs) => (errs[field] ? { ...errs, [field]: undefined } : errs))
    }
  }

  function validate() {
    const errs = {}
    if (!form.full_name.trim()) errs.full_name = 'Full name is required.'
    if (!form.email.trim()) errs.email = 'Email is required.'
    else if (!EMAIL_RE.test(form.email.trim())) errs.email = 'Enter a valid email address.'
    if (!form.password) errs.password = 'Password is required.'
    else if (form.password.length < MIN_PASSWORD)
      errs.password = `Must be at least ${MIN_PASSWORD} characters.`
    if (form.confirm !== form.password) errs.confirm = 'Passwords do not match.'
    setFieldErrors(errs)
    return Object.keys(errs).length === 0
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    if (!validate()) return
    setBusy(true)
    try {
      await apiRegister({
        email: form.email.trim(),
        full_name: form.full_name.trim(),
        password: form.password,
      })
      // Auto-login so the new account lands straight in the app.
      const data = await apiLogin(form.email.trim(), form.password)
      loginSession(data)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      // Backend duplicate returns 400 "Email already registered" — surface it
      // inline (not a generic failure).
      setError(err.message || 'Sign up failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-paper px-4">
      <div className="mb-6 flex items-center gap-2.5">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand text-white">
          <CheckCircle2 className="h-5 w-5" />
        </span>
        <span className="font-display text-lg font-semibold tracking-tight text-ink">Onboard Chaser</span>
      </div>

      <Card className="w-full max-w-sm p-7">
        <h1 className="font-display text-xl font-semibold text-ink">Create an HR account</h1>
        <p className="mt-1 text-sm text-ink-soft">Set up sign-in to manage onboardings.</p>

        {error && (
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-danger/25 bg-danger-soft px-3.5 py-3 text-[13px] text-danger">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <FormField label="Full name" id="full_name" value={form.full_name} onChange={update('full_name')}
            error={fieldErrors.full_name} placeholder="Mohammad Yousefi" autoComplete="name" />
          <FormField label="Email" id="email" type="email" value={form.email} onChange={update('email')}
            error={fieldErrors.email} placeholder="hr@company.com" autoComplete="email" />
          <FormField label="Password" id="password" type="password" value={form.password} onChange={update('password')}
            error={fieldErrors.password} placeholder="At least 8 characters" autoComplete="new-password" hint={`At least ${MIN_PASSWORD} characters`} />
          <FormField label="Confirm password" id="confirm" type="password" value={form.confirm} onChange={update('confirm')}
            error={fieldErrors.confirm} placeholder="Repeat password" autoComplete="new-password" />

          <Button type="submit" disabled={busy} className="w-full">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Create account'}
          </Button>
        </form>

        <p className="mt-5 border-t border-border-soft pt-4 text-center text-[13px] text-ink-soft">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-brand-dark hover:underline">Log in</Link>
        </p>
      </Card>
    </div>
  )
}

function FormField({ label, id, type = 'text', value, onChange, error, placeholder, autoComplete, hint }) {
  const invalid = Boolean(error)
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-medium text-ink">{label}</span>
      <input
        id={id}
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        autoComplete={autoComplete}
        aria-invalid={invalid}
        className={`h-10 w-full rounded-lg border bg-surface px-3 text-[13.5px] text-ink focus:outline-none ${
          invalid ? 'border-danger' : 'border-border focus:border-brand'
        }`}
      />
      {error ? (
        <span className="mt-1 block text-xs text-danger">{error}</span>
      ) : hint ? (
        <span className="mt-1 block text-xs text-ink-faint">{hint}</span>
      ) : null}
    </label>
  )
}
