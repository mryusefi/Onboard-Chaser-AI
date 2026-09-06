import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { CheckCircle2, Loader2, AlertCircle } from 'lucide-react'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { login as apiLogin } from '../api/client'
import { useAuth } from '../context/AuthContext'

// US12-frontend — HR login (new; the prototype had no auth screen).
// Backed by POST /api/v1/auth/login (JSON {email, password}); stores the JWT
// via the api client (localStorage 'hr_token') and the user info in
// AuthContext. Register remains an API-only flow (US01), no UI.

export default function Login() {
  const navigate = useNavigate()
  const { login: loginSession } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const data = await apiLogin(email, password)
      loginSession(data)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(err.message || 'Login failed')
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
        <h1 className="font-display text-xl font-semibold text-ink">HR sign in</h1>
        <p className="mt-1 text-sm text-ink-soft">Manage onboardings, documents and reminders.</p>

        {error && (
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-danger/25 bg-danger-soft px-3.5 py-3 text-[13px] text-danger">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <label className="block">
            <span className="mb-1.5 block text-[13px] font-medium text-ink">Email</span>
            <input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="hr@company.com"
              autoComplete="username"
              className="h-10 w-full rounded-lg border border-border bg-surface px-3 text-[13.5px] text-ink focus:border-brand focus:outline-none"
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-[13px] font-medium text-ink">Password</span>
            <input
              required
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              className="h-10 w-full rounded-lg border border-border bg-surface px-3 text-[13.5px] text-ink focus:border-brand focus:outline-none"
            />
          </label>
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Sign in'}
          </Button>
        </form>

        <p className="mt-5 border-t border-border-soft pt-4 text-xs text-ink-faint">
          First time setup: register the HR account via{' '}
          <code className="font-mono text-[11px]">POST /api/v1/auth/register</code> (no UI by
          design in the MVP). Candidates never sign in — they use magic links.
        </p>
      </Card>
    </div>
  )
}
