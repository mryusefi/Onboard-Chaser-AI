import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Plus, Trash2, CheckCircle2, AlertCircle, Loader2, ArrowLeft, Mail } from 'lucide-react'
import ReminderHistory from '../components/ReminderHistory'

const DEFAULT_DOCS = [
  { name: 'Government ID', description: '', instructions: 'Upload a clear photo/scan of your government-issued ID.', accepted_formats: 'PDF, JPG, PNG', required: true },
  { name: 'Proof of Address', description: '', instructions: 'Upload a recent utility bill or bank statement.', accepted_formats: 'PDF, JPG, PNG', required: true },
  { name: 'Tax Form (W-4)', description: '', instructions: 'Download, complete and sign the IRS W-4 form.', accepted_formats: 'PDF', required: true },
  { name: 'Signed Offer Letter', description: '', instructions: 'Upload the signed copy of your offer letter.', accepted_formats: 'PDF, JPG, PNG', required: true },
]

export default function CreateOnboardingPage() {
  const navigate = useNavigate()
  const [candidate, setCandidate] = useState({ full_name: '', email: '', phone: '', position: '' })
  // Which of the 4 default docs are included (default: all)
  const [selectedDefaults, setSelectedDefaults] = useState(DEFAULT_DOCS.map(() => true))
  // Custom additional documents added by HR
  const [customDocs, setCustomDocs] = useState([])
  const [customDraft, setCustomDraft] = useState({ name: '', description: '', instructions: '', accepted_formats: 'PDF, JPG, PNG' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  const updateCandidate = (k) => (e) => setCandidate({ ...candidate, [k]: e.target.value })

  const toggleDefault = (i) => {
    const next = [...selectedDefaults]
    next[i] = !next[i]
    setSelectedDefaults(next)
  }

  const addCustomDoc = () => {
    if (!customDraft.name.trim()) return
    setCustomDocs([...customDocs, { ...customDraft }])
    setCustomDraft({ name: '', description: '', instructions: '', accepted_formats: 'PDF, JPG, PNG' })
  }

  const removeCustomDoc = (i) => {
    setCustomDocs(customDocs.filter((_, idx) => idx !== i))
  }

  const submit = async (e) => {
    e.preventDefault()
    setError(null)

    if (!candidate.full_name.trim() || !candidate.email.trim()) {
      setError('Full name and email are required.')
      return
    }

    // Build the required_documents payload: selected defaults + custom docs.
    // If all defaults are kept and no custom docs exist, omit the list so the
    // backend seeds the defaults itself.
    const chosenDefaults = DEFAULT_DOCS.filter((_, i) => selectedDefaults[i])
    const allChosen = chosenDefaults.length === DEFAULT_DOCS.length
    let required_documents
    if (allChosen && customDocs.length === 0) {
      required_documents = undefined
    } else {
      required_documents = [
        ...chosenDefaults.map((d) => ({ ...d })),
        ...customDocs.map((d) => ({ ...d })),
      ]
    }

    setLoading(true)
    try {
      const resp = await fetch('/api/v1/onboarding/create-full', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate,
          ...(required_documents ? { required_documents } : {}),
        }),
      })
      const data = await resp.json()
      if (!resp.ok) {
        throw new Error(data.detail || 'Failed to create onboarding')
      }
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // ---------- Success summary ----------
  if (result) {
    return (
      <InvitationPanel
        result={result}
        onReset={() => window.location.reload()}
      />
    )
  }

  // ---------- Form ----------
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 py-10 px-4">
      <div className="max-w-2xl mx-auto">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 mb-4"
        >
          <ArrowLeft className="w-4 h-4" /> Back to home
        </button>

        <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-8">
          <h1 className="text-2xl font-bold text-slate-900 mb-1">New Onboarding</h1>
          <p className="text-sm text-slate-500 mb-6">Create a candidate and collect their documents.</p>

          {error && (
            <div className="mb-5 flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              {error}
            </div>
          )}

          <form onSubmit={submit} className="space-y-6">
            {/* Candidate info */}
            <fieldset className="space-y-3">
              <legend className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Candidate Information</legend>
              <input value={candidate.full_name} onChange={updateCandidate('full_name')} placeholder="Full name *"
                className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500" />
              <input type="email" value={candidate.email} onChange={updateCandidate('email')} placeholder="Email *"
                className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500" />
              <div className="grid grid-cols-2 gap-3">
                <input value={candidate.phone} onChange={updateCandidate('phone')} placeholder="Phone"
                  className="px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500" />
                <input value={candidate.position} onChange={updateCandidate('position')} placeholder="Position"
                  className="px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500" />
              </div>
            </fieldset>

            {/* Default documents */}
            <fieldset>
              <legend className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Required Documents</legend>
              <div className="space-y-2">
                {DEFAULT_DOCS.map((d, i) => (
                  <label key={d.name} className="flex items-center gap-3 px-4 py-2.5 rounded-xl border border-slate-200 cursor-pointer hover:bg-slate-50">
                    <input type="checkbox" checked={selectedDefaults[i]} onChange={() => toggleDefault(i)}
                      className="w-4 h-4 accent-primary-600" />
                    <span className="text-sm font-medium text-slate-800">{d.name}</span>
                  </label>
                ))}
              </div>

              {/* Custom documents */}
              {customDocs.length > 0 && (
                <ul className="mt-3 space-y-2">
                  {customDocs.map((d, i) => (
                    <li key={i} className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-dashed border-primary-300 bg-primary-50">
                      <FileText className="w-4 h-4 text-primary-600" />
                      <span className="text-sm font-medium text-slate-800 flex-1">{d.name}</span>
                      <button type="button" onClick={() => removeCustomDoc(i)} className="text-slate-400 hover:text-red-500">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              {/* Add custom doc */}
              <div className="mt-3 space-y-2">
                <div className="grid grid-cols-[1fr_auto] gap-2">
                  <input value={customDraft.name} onChange={(e) => setCustomDraft({ ...customDraft, name: e.target.value })}
                    placeholder="Custom document name"
                    className="px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500" />
                  <button type="button" onClick={addCustomDoc}
                    className="flex items-center gap-1 px-4 py-2.5 rounded-xl bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200">
                    <Plus className="w-4 h-4" /> Add
                  </button>
                </div>
                <input value={customDraft.instructions} onChange={(e) => setCustomDraft({ ...customDraft, instructions: e.target.value })}
                  placeholder="Instructions (optional)"
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500" />
                <input value={customDraft.accepted_formats} onChange={(e) => setCustomDraft({ ...customDraft, accepted_formats: e.target.value })}
                  placeholder="Accepted formats (e.g. PDF, JPG, PNG)"
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500" />
              </div>
            </fieldset>

            <button type="submit" disabled={loading}
              className="w-full py-3 rounded-xl font-semibold text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2">
              {loading ? (<><Loader2 className="w-5 h-5 animate-spin" /> Creating…</>) : 'Create Onboarding'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}


function InvitationPanel({ result, onReset }) {
  const onboardingId = result.onboarding.id
  const [invite, setInvite] = useState(null)   // response from send-invitation
  const [invStatus, setInvStatus] = useState('not_sent')
  const [sending, setSending] = useState(false)
  const [inviteError, setInviteError] = useState(null)
  const [copied, setCopied] = useState(false)

  const sendInvitation = async () => {
    setSending(true)
    setInviteError(null)
    try {
      const resp = await fetch(`/api/v1/onboarding/${onboardingId}/send-invitation`, { method: 'POST' })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.detail || 'Failed to send invitation')
      setInvite(data)
      setInvStatus(data.status)
    } catch (err) {
      setInviteError(err.message)
    } finally {
      setSending(false)
    }
  }

  const copyLink = async () => {
    const url = invite?.portal_url
    if (!url) return
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard unavailable (insecure context) — ignore
    }
  }

  const statusStyles = {
    not_sent: 'bg-slate-100 text-slate-600',
    sent: 'bg-blue-100 text-blue-700',
    failed: 'bg-red-100 text-red-700',
    delivered: 'bg-green-100 text-green-700',
    bounced: 'bg-orange-100 text-orange-700',
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 py-10 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-8">
          <div className="flex items-center gap-3 mb-6">
            <CheckCircle2 className="w-8 h-8 text-green-500" />
            <h1 className="text-2xl font-bold text-slate-900">Onboarding Created</h1>
          </div>

          <div className="space-y-4 mb-6">
            <div className="bg-slate-50 rounded-xl p-4">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Candidate</p>
              <p className="text-base font-medium text-slate-900">{result.candidate.full_name}</p>
              <p className="text-sm text-slate-600">{result.candidate.email}</p>
              {result.candidate.position && (
                <p className="text-sm text-slate-500">Position: {result.candidate.position}</p>
              )}
            </div>
            <div className="bg-slate-50 rounded-xl p-4">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Onboarding</p>
              <p className="text-sm text-slate-700">
                Status: <span className="font-medium capitalize">{result.onboarding.status}</span>
              </p>
              <p className="text-sm text-slate-700">{result.documents.length} documents requested</p>
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Required Documents</p>
              <ul className="space-y-2">
                {result.documents.map((doc) => (
                  <li key={doc.id} className="flex items-center gap-2 text-sm text-slate-700">
                    <FileText className="w-4 h-4 text-primary-500 shrink-0" />
                    <span className="font-medium">{doc.name}</span>
                    {!doc.required && <span className="text-xs text-slate-400">(optional)</span>}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* ── US07: Invitation panel ─────────────────────────────── */}
          <div className="border-t border-slate-200 pt-6 mb-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-semibold text-slate-900">Invitation</h2>
              <span className={`text-xs font-semibold px-3 py-1 rounded-full capitalize ${statusStyles[invStatus] || statusStyles.not_sent}`}>
                {invStatus.replace('_', ' ')}
              </span>
            </div>

            {inviteError && (
              <div className="mb-3 flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                {inviteError}
              </div>
            )}

            {invite?.last_error && (
              <p className="mb-3 text-xs text-red-600">Provider error: {invite.last_error}</p>
            )}

            <div className="flex flex-col sm:flex-row gap-3">
              <button
                onClick={sendInvitation}
                disabled={sending}
                className="flex-1 py-2.5 rounded-xl font-semibold text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {sending ? (<><Loader2 className="w-4 h-4 animate-spin" /> Sending…</>) : (<><Mail className="w-4 h-4" /> Send Invitation</>)}
              </button>
              {invite?.portal_url && (
                <button
                  onClick={copyLink}
                  className="py-2.5 px-4 rounded-xl font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 transition-colors text-sm"
                >
                  {copied ? 'Copied!' : 'Copy portal link'}
                </button>
              )}
            </div>

            {invite && (
              <div className="mt-3 text-xs text-slate-500 space-y-1">
                <p>
                  Email configured: <span className="font-medium">{invite.email_configured ? 'yes' : 'no'}</span>
                  {!invite.email_configured && ' — set RESEND_API_KEY to enable real sending; link below still works.'}
                </p>
                <p>Link expires in {invite.expiry_hours} hours.</p>
                {invite.portal_url && (
                  <p className="break-all">
                    <span className="font-medium">Portal link:</span>{' '}
                    <a href={invite.portal_url} target="_blank" rel="noreferrer" className="text-primary-600 hover:underline">
                      {invite.portal_url}
                    </a>
                  </p>
                )}
              </div>
            )}
          </div>

          {/* ── US08/US09: Reminder history + manual trigger ─────────── */}
          <ReminderHistory onboardingId={onboardingId} />

          <button
            onClick={onReset}
            className="w-full py-3 rounded-xl font-semibold text-white bg-primary-600 hover:bg-primary-700 transition-colors mt-6"
          >
            Create Another Onboarding
          </button>
        </div>
      </div>
    </div>
  )
}
