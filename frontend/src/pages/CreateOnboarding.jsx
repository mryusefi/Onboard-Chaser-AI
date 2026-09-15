import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, Link2, Send, Loader2, Plus, Trash2, Wand2 } from 'lucide-react'
import Topbar from '../components/Topbar'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Modal from '../components/ui/Modal'
import { useOnboarding } from '../context/OnboardingContext'
import { useToast } from '../context/ToastContext'
import { generateMagicLink, sendInvitation } from '../api/client'

// Maintenance pass Part C: fully custom required-document builder.
// The old "4 default checkboxes" became: an editable list (add/remove per
// row) with name + optional instructions + a type selector, plus a
// "Load standard 4 documents" one-click prefill HR can still edit/remove.
// Submitting with an EMPTY list sends no required_documents -> backend seeds
// its standard defaults. Max 20 documents is enforced both client & server.

const DOC_TYPES = [
  { value: 'image', label: 'Image (JPG, PNG, GIF)' },
  { value: 'pdf_document', label: 'PDF document' },
  { value: 'file', label: 'Any file (PDF, JPG, PNG)' },
]
const TYPE_LABEL = Object.fromEntries(DOC_TYPES.map((t) => [t.value, t.label.split(' ')[0]]))
const MAX_DOCS = 20

// Mirror of backend DEFAULT_DOCUMENTS — prefill shortcut only (editable).
const STANDARD_DOCS = [
  { name: 'Government ID', document_type: 'file' },
  { name: 'Proof of Address', document_type: 'file' },
  { name: 'Tax Form (W-4)', document_type: 'pdf_document' },
  { name: 'Signed Offer Letter', document_type: 'file' },
]

let docSeq = 0
const nextId = () => `doc-${++docSeq}`

export default function CreateOnboarding() {
  const { createOnboarding } = useOnboarding()
  const { showToast } = useToast()

  const [form, setForm] = useState({ full_name: '', email: '', phone: '', position: '' })
  const [docs, setDocs] = useState([]) // {id, name, document_type, instructions}
  const [docErrors, setDocErrors] = useState({})
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState(null)
  const [created, setCreated] = useState(null)
  const [inviting, setInviting] = useState(false)
  const [inviteStatus, setInviteStatus] = useState(null)
  const [copied, setCopied] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)

  function updateCandidate(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  function addDoc() {
    setDocs((d) => [...d, { id: nextId(), name: '', document_type: 'file', instructions: '' }])
  }

  function loadStandard() {
    setDocs(STANDARD_DOCS.map((d) => ({ id: nextId(), name: d.name, document_type: d.document_type, instructions: '' })))
  }

  function patchDoc(id, field, value) {
    setDocs((ds) => ds.map((d) => (d.id === id ? { ...d, [field]: value } : d)))
  }

  function removeDoc(id) {
    setDocs((ds) => ds.filter((d) => d.id !== id))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    const errs = {}
    docs.forEach((d, i) => {
      if (!d.name.trim()) errs[d.id] = 'Name is required'
    })
    setDocErrors(errs)
    if (Object.keys(errs).length > 0) return

    setCreating(true)
    try {
      const result = await createOnboarding({
        candidate: form,
        required_documents: docs.length
          ? docs.map((d) => ({
              name: d.name.trim(),
              document_type: d.document_type,
              ...(d.instructions.trim() ? { instructions: d.instructions.trim() } : {}),
            }))
          : undefined, // empty list -> backend seeds standard defaults
      })
      setCreated(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setCreating(false)
    }
  }

  async function handleCopyLink() {
    if (!created) return
    try {
      const data = await generateMagicLink(created.candidate.id)
      navigator.clipboard?.writeText(data.magic_link).catch(() => {})
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      showToast(err.message)
    }
  }

  async function handleSendInvitation() {
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

  function handleStartAnother() {
    setForm({ full_name: '', email: '', phone: '', position: '' })
    setDocs([])
    setDocErrors({})
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
            <div className="mt-4 space-y-1.5 text-left">
              {created.documents.map((d) => (
                <div key={d.id} className="flex items-center justify-between rounded-lg border border-border-soft bg-surface-sunken/40 px-3 py-2">
                  <span className="text-[13px] text-ink">{d.name}</span>
                  <Badge status="pending" withIcon={false} className="!bg-surface !text-ink-soft">
                    {d.document_type ? TYPE_LABEL[d.document_type] || d.document_type : 'Any file'}
                  </Badge>
                </div>
              ))}
            </div>
            <div className="mt-5 flex flex-wrap items-center justify-center gap-2.5">
              <Button variant="secondary" size="sm" icon={Link2} onClick={handleCopyLink}>
                {copied ? 'Copied!' : 'Copy portal link'}
              </Button>
              <Button size="sm" icon={Send} onClick={() => setConfirmOpen(true)}>Send invitation</Button>
            </div>
            {inviteStatus && (
              <p className={`mt-4 text-[13px] font-medium ${inviteStatus === 'sent' ? 'text-success' : 'text-warning'}`}>
                Invitation {inviteStatus.replace(/_/g, ' ')}
                {inviteStatus !== 'sent' && ' — check RESEND_API_KEY configuration'}
              </p>
            )}
            <div className="mt-6 border-t border-border-soft pt-5">
              <Link to="/onboardings" className="text-[13px] font-medium text-brand-dark hover:underline">Go to onboardings</Link>
              <span className="mx-2 text-ink-faint">·</span>
              <button onClick={handleStartAnother} className="text-[13px] font-medium text-ink-soft hover:text-ink">Create another</button>
            </div>
          </Card>
        </div>
        <Modal open={confirmOpen} onClose={() => setConfirmOpen(false)} title="Send onboarding invitation"
          footer={<>
            <Button variant="secondary" onClick={() => setConfirmOpen(false)}>Cancel</Button>
            <Button icon={inviting ? Loader2 : Send} disabled={inviting} onClick={handleSendInvitation}>
              {inviting ? 'Sending…' : 'Send invitation'}
            </Button>
          </>}>
          <p className="text-[13.5px] text-ink-soft">
            Sends the onboarding email to <span className="font-medium text-ink">{created.candidate.email}</span>
            {' '}with a secure, expiring magic link to their portal.
          </p>
        </Modal>
      </div>
    )
  }

  return (
    <div className="pb-16">
      <Topbar eyebrow="Onboardings" title="Create onboarding" subtitle="Set up a secure portal for a new candidate." />
      <div className="px-8 py-7">
        {error && (
          <div className="mx-auto mb-4 max-w-xl rounded-xl border border-danger/25 bg-danger-soft px-4 py-3 text-sm text-danger">{error}</div>
        )}
        <Card className="mx-auto max-w-2xl p-7">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Candidate name"><input required value={form.full_name} onChange={(e) => updateCandidate('full_name', e.target.value)} placeholder="Sara Ahmadi" className="input" /></Field>
              <Field label="Candidate email"><input required type="email" value={form.email} onChange={(e) => updateCandidate('email', e.target.value)} placeholder="sara@example.com" className="input" /></Field>
              <Field label="Phone (optional)"><input value={form.phone} onChange={(e) => updateCandidate('phone', e.target.value)} placeholder="+1 555 000 0000" className="input" /></Field>
              <Field label="Position"><input required value={form.position} onChange={(e) => updateCandidate('position', e.target.value)} placeholder="Product Manager" className="input" /></Field>
            </div>

            {/* Custom required documents builder (Part C) */}
            <div>
              <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
                <p className="text-[13px] font-medium text-ink">Required documents</p>
                <div className="flex items-center gap-2">
                  <Button type="button" variant="ghost" size="sm" icon={Wand2} onClick={loadStandard}>
                    Load standard 4
                  </Button>
                  <Button type="button" variant="secondary" size="sm" icon={Plus} disabled={docs.length >= MAX_DOCS} onClick={addDoc}>
                    Add document
                  </Button>
                </div>
              </div>

              {docs.length === 0 ? (
                <p className="rounded-lg border border-dashed border-border bg-surface-sunken/40 px-3.5 py-3 text-xs text-ink-faint">
                  No custom documents yet — submitting now seeds the 4 standard defaults (Government ID,
                  Proof of Address, Tax Form W-4, Signed Offer Letter). Use “Load standard 4” to start
                  from them and edit freely, or add your own ({MAX_DOCS} max).
                </p>
              ) : (
                <ul className="space-y-2.5">
                  {docs.map((d) => (
                    <li key={d.id} className="rounded-xl border border-border bg-surface p-3">
                      <div className="flex items-center gap-2">
                        <input
                          value={d.name}
                          onChange={(e) => patchDoc(d.id, 'name', e.target.value)}
                          placeholder="Document name *"
                          aria-invalid={Boolean(docErrors[d.id])}
                          className={`h-9 flex-1 rounded-lg border bg-surface px-3 text-[13.5px] text-ink focus:outline-none ${
                            docErrors[d.id] ? 'border-danger' : 'border-border focus:border-brand'
                          }`}
                        />
                        <select
                          value={d.document_type}
                          onChange={(e) => patchDoc(d.id, 'document_type', e.target.value)}
                          className="h-9 rounded-lg border border-border bg-surface px-2 text-[13px] text-ink focus:border-brand focus:outline-none"
                        >
                          {DOC_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                        </select>
                        <button type="button" onClick={() => removeDoc(d.id)} aria-label="Remove document"
                          className="rounded-lg p-2 text-ink-faint hover:bg-danger-soft hover:text-danger">
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                      {docErrors[d.id] && <p className="mt-1 text-xs text-danger">{docErrors[d.id]}</p>}
                      <input
                        value={d.instructions}
                        onChange={(e) => patchDoc(d.id, 'instructions', e.target.value)}
                        placeholder="Instructions for the candidate (optional)"
                        className="mt-2 h-9 w-full rounded-lg border border-border bg-surface px-3 text-[13px] text-ink placeholder:text-ink-faint focus:border-brand focus:outline-none"
                      />
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="flex items-center justify-between border-t border-border-soft pt-5">
              <Link to="/onboardings" className="flex items-center gap-1.5 text-[13px] font-medium text-ink-soft hover:text-ink">
                <ArrowLeft className="h-3.5 w-3.5" /> Cancel
              </Link>
              <Button type="submit" disabled={creating} icon={creating ? Loader2 : undefined}>
                {creating ? 'Creating…' : 'Create onboarding'}
              </Button>
            </div>
          </form>
        </Card>
      </div>
      <style>{`
        .input { height: 2.5rem; width: 100%; border-radius: 0.5rem; border: 1px solid var(--color-border, #E5E4DE);
          background: var(--color-surface, #fff); padding: 0 0.75rem; font-size: 13.5px; color: var(--color-ink, #14171F); }
        .input:focus { border-color: #0B6E6E; outline: none; }
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
