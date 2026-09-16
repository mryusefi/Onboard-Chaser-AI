import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, Link2, Copy, Send, Loader2 } from 'lucide-react'
import Topbar from '../components/Topbar'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Modal from '../components/ui/Modal'
import { useOnboarding } from '../context/OnboardingContext'
import { useToast } from '../context/ToastContext'
import { generateMagicLink, sendInvitation } from '../api/client'

// US12-frontend: real create flow — POST /onboarding/create-full (US06)
// creates candidate + onboarding + seeded default documents in one call,
// then POST /onboarding/{id}/send-invitation (US07) sends the email.
// Decision documented: create and invite are two steps (invite is optional
// so HR can review first); the magic link is generated server-side and
// shown for manual copy/share.

const initialForm = { full_name: '', email: '', phone: '', position: '' }

export default function CreateOnboarding() {
  const { createOnboarding } = useOnboarding()
  const { showToast } = useToast()
  const navigate = useNavigate()

  const [form, setForm] = useState(initialForm)
  const [creating, setCreating] = useState(false)
  const [created, setCreated] = useState(null) // { onboarding, candidate, documents }
  const [inviting, setInviting] = useState(false)
  const [inviteStatus, setInviteStatus] = useState(null) // response.status
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState(null)
  const [confirmOpen, setConfirmOpen] = useState(false)

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.full_name.trim() || !form.email.trim()) return
    setCreating(true)
    setError(null)
    try {
      const result = await createOnboarding({ candidate: form })
      setCreated(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setCreating(false)
    }
  }

  async function handleSendInvitation() {
    if (!created) return
    setInviting(true)
    try {
      const result = await sendInvitation(created.onboarding.id)
      setInviteStatus(result?.status || 'not_sent')
      setConfirmOpen(false)
    } catch (err) {
      showToast(err.message)
    } finally {
      setInviting(false)
    }
  }

  async function handleCopyLink() {
    if (!created) return
    try {
      // create-full does not return the token; request a fresh magic link
      // (US01) so HR can copy/share it directly.
      const data = await generateMagicLink(created.candidate.id)
      navigator.clipboard?.writeText(data.magic_link).catch(() => {})
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      showToast(err.message)
    }
  }

  function handleStartAnother() {
    setForm(initialForm)
    setCreated(null)
    setInviteStatus(null)
    setError(null)
  }

  if (created) {
    return (
      <div className="pb-16">
        <Topbar eyebrow="Create onboarding" title="Onboarding created" />
        <div className="px-8 py-8">
          <Card className="mx-auto max-w-lg p-8 text-center">
            <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-success-soft text-success">
              <CheckCircle2 className="h-6 w-6" />
            </span>
            <h2 className="mt-4 font-display text-xl font-semibold text-ink">Onboarding created</h2>
            <p className="mt-1.5 text-sm text-ink-soft">
              Candidate <span className="font-medium text-ink">{created.candidate.full_name}</span>
            </p>
            <p className="text-sm text-ink-soft">
              {created.documents.length} required document{created.documents.length === 1 ? '' : 's'} requested.
            </p>

            <div className="mt-5 flex flex-wrap items-center justify-center gap-2.5">
              <Button variant="secondary" size="sm" icon={Link2} onClick={handleCopyLink}>
                {copied ? 'Copied!' : 'Copy portal link'}
              </Button>
              <Button size="sm" icon={Send} onClick={() => setConfirmOpen(true)}>
                Send invitation
              </Button>
            </div>

            {inviteStatus && (
              <p
                className={`mt-4 flex items-center justify-center gap-1.5 text-[13px] font-medium ${
                  inviteStatus === 'sent' ? 'text-success' : 'text-warning'
                }`}
              >
                <CheckCircle2 className="h-4 w-4" />
                Invitation {inviteStatus.replace(/_/g, ' ')}
                {inviteStatus !== 'sent' && ' — check RESEND_API_KEY configuration'}
              </p>
            )}

            <div className="mt-6 border-t border-border-soft pt-5">
              <Link to="/onboardings" className="text-[13px] font-medium text-brand-dark hover:underline">
                Go to onboardings
              </Link>
              <span className="mx-2 text-ink-faint">·</span>
              <button onClick={handleStartAnother} className="text-[13px] font-medium text-ink-soft hover:text-ink">
                Create another
              </button>
            </div>
          </Card>
        </div>

        <Modal
          open={confirmOpen}
          onClose={() => setConfirmOpen(false)}
          title="Send onboarding invitation"
          footer={
            <>
              <Button variant="secondary" onClick={() => setConfirmOpen(false)}>
                Cancel
              </Button>
              <Button icon={inviting ? Loader2 : Send} disabled={inviting} onClick={handleSendInvitation}>
                {inviting ? 'Sending…' : 'Send invitation'}
              </Button>
            </>
          }
        >
          <div className="space-y-3 text-[13.5px]">
            <p className="text-ink-soft">
              Sends the onboarding email to{' '}
              <span className="font-medium text-ink">{created.candidate.email}</span> with a
              secure, expiring magic link to their portal.
            </p>
            <p className="text-xs text-ink-faint">
              Requires RESEND_API_KEY to be configured; without it the attempt is recorded
              as not_sent and no email goes out.
            </p>
          </div>
        </Modal>
      </div>
    )
  }

  return (
    <div className="pb-16">
      <Topbar
        eyebrow="Onboardings"
        title="Create onboarding"
        subtitle="Set up a secure portal for a new candidate."
      />

      <div className="px-8 py-7">
        {error && (
          <div className="mx-auto mb-4 max-w-xl rounded-xl border border-danger/25 bg-danger-soft px-4 py-3 text-sm text-danger">
            {error}
          </div>
        )}

        <Card className="mx-auto max-w-xl p-7">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Candidate name">
                <input
                  required
                  value={form.full_name}
                  onChange={(e) => update('full_name', e.target.value)}
                  placeholder="Sara Ahmadi"
                  className="input"
                />
              </Field>
              <Field label="Candidate email">
                <input
                  required
                  type="email"
                  value={form.email}
                  onChange={(e) => update('email', e.target.value)}
                  placeholder="sara@example.com"
                  className="input"
                />
              </Field>
              <Field label="Phone (optional)">
                <input
                  value={form.phone}
                  onChange={(e) => update('phone', e.target.value)}
                  placeholder="+1 555 000 0000"
                  className="input"
                />
              </Field>
              <Field label="Position">
                <input
                  required
                  value={form.position}
                  onChange={(e) => update('position', e.target.value)}
                  placeholder="Product Manager"
                  className="input"
                />
              </Field>
            </div>

            <p className="rounded-lg border border-dashed border-border bg-surface-sunken/50 px-3.5 py-2.5 text-xs text-ink-faint">
              The four standard required documents (Government ID, Proof of Address, Tax Form
              W-4, Signed Offer Letter) are seeded automatically.
            </p>

            <div className="flex items-center justify-between border-t border-border-soft pt-5">
              <button
                type="button"
                onClick={() => navigate('/onboardings')}
                className="flex items-center gap-1.5 text-[13px] font-medium text-ink-soft hover:text-ink"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                Cancel
              </button>
              <Button type="submit" disabled={creating} icon={creating ? Loader2 : undefined}>
                {creating ? 'Creating…' : 'Create onboarding'}
              </Button>
            </div>
          </form>
        </Card>
      </div>

      <style>{`
        .input {
          height: 2.5rem;
          width: 100%;
          border-radius: 0.5rem;
          border: 1px solid var(--color-border);
          background: var(--color-surface);
          padding: 0 0.75rem;
          font-size: 13.5px;
          color: var(--color-ink);
        }
        .input:focus {
          border-color: var(--color-brand);
          outline: none;
        }
      `}</style>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-medium text-ink">{label}</span>
      {children}
    </label>
  )
}
