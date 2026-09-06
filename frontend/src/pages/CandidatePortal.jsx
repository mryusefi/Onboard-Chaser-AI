import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  CheckCircle2, ShieldCheck, Lock, UserX, Loader2, AlertCircle, FileText, Clock,
} from 'lucide-react'
import ProgressBar from '../components/ui/ProgressBar'
import DocumentRow from '../components/DocumentRow'
import FileUpload from '../components/ui/FileUpload'
import { fetchPortal } from '../api/client'

// US12-frontend — candidate portal, reached ONLY via /onboard/:token.
// SECURITY DECISION (do not "fix" back to /candidate/:candidateId): the
// candidate-facing flow is authorized by a signed, expiring magic-link token
// (README section 8). A guessable numeric candidate ID would let anyone open
// anyone else's onboarding. The prototype's ID-based route is deliberately
// NOT carried over; only the visual skin was adopted.

const SECURITY_NOTES = [
  { Icon: ShieldCheck, text: 'Your documents are encrypted (AES-256) before storage.' },
  { Icon: Lock, text: 'Your onboarding link is private and expires.' },
  { Icon: UserX, text: "You don't need to create an account." },
]

function formatBytes(size) {
  if (!size) return ''
  const n = parseInt(size, 10)
  if (Number.isNaN(n)) return size
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export default function CandidatePortal() {
  const { token } = useParams()
  const [portal, setPortal] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchPortal(token)
      setPortal(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    load()
  }, [load])

  async function handleUpload(doc) {
    // FileUpload performs the real POST and shows its own progress/error;
    // this callback refreshes server-recomputed status/progress and may
    // auto-complete the onboarding (US05).
    await load()
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-24 text-sm text-ink-faint">
        <Loader2 className="h-6 w-6 animate-spin text-brand" />
        Validating your secure access…
      </div>
    )
  }

  if (error) {
    return (
      <div className="py-16 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-danger-soft">
          <AlertCircle className="h-6 w-6 text-danger" />
        </div>
        <p className="mt-4 text-sm font-medium text-ink">This onboarding link isn't valid.</p>
        <p className="mt-1 text-sm text-ink-faint">{error}</p>
        <p className="mt-4 text-xs text-ink-faint">
          The link may have expired. Please request a new onboarding link from your HR team.
        </p>
      </div>
    )
  }

  const percent = portal.completion_percentage ?? 0
  const completed = portal.completed_documents ?? 0
  const total = portal.total_documents ?? 0
  const isComplete = percent === 100
  const firstName = (portal.candidate_name || '').split(' ')[0]

  const portalDocs = portal.documents.map((d) => ({
    ...d,
    // DocumentRow portal variant reads file_name/uploaded_at; the portal
    // payload has the same names, so this is a pass-through.
  }))

  return (
    <div>
      {isComplete ? (
        <div className="mb-8 flex flex-col items-center rounded-2xl border border-success/20 bg-success-soft px-6 py-8 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-success text-white">
            <CheckCircle2 className="h-6 w-6" />
          </span>
          <h1 className="mt-4 font-display text-xl font-semibold text-ink">You're all set!</h1>
          <p className="mt-1.5 max-w-sm text-sm text-ink-soft">
            All required onboarding documents have been submitted.
          </p>
          <p className="mt-3 text-[13px] font-medium text-success">
            ✓ {total} of {total} documents completed
          </p>
        </div>
      ) : (
        <div className="mb-8">
          <h1 className="font-display text-xl font-semibold tracking-tight text-ink">
            Welcome, {firstName}
          </h1>
          <p className="mt-1.5 text-sm text-ink-soft">
            Complete your onboarding documents before your start date.
          </p>

          <div className="mt-5 max-w-md">
            <div className="mb-1.5 flex items-center justify-between text-[13px]">
              <span className="font-medium text-ink">Progress</span>
              <span className="tabular font-mono text-ink-soft">{percent}%</span>
            </div>
            <ProgressBar percent={percent} size="lg" />
            <p className="mt-1.5 text-xs text-ink-faint">
              {completed} of {total} documents completed
            </p>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {portalDocs.length === 0 && (
          <div className="rounded-2xl border border-dashed border-border py-12 text-center">
            <FileText className="mx-auto h-8 w-8 text-ink-faint" />
            <p className="mt-2 text-sm text-ink-soft">No documents requested yet.</p>
          </div>
        )}
        {portalDocs.map((doc) => (
          <DocumentRow key={doc.id} doc={doc} variant="portal">
            {isComplete ? null : (
              <FileUpload
                key={`${doc.id}-${doc.file_name || 'empty'}`}
                documentId={doc.id}
                onUploadComplete={() => handleUpload(doc)}
              />
            )}
          </DocumentRow>
        ))}
      </div>

      {error && (
        <div className="mt-4 flex items-start gap-2 rounded-xl border border-danger/25 bg-danger-soft px-4 py-3 text-sm text-danger">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      <div className="mt-9 flex flex-col gap-2.5 border-t border-border-soft pt-6">
        {SECURITY_NOTES.map(({ Icon, text }) => (
          <div key={text} className="flex items-center gap-2 text-xs text-ink-faint">
            <Icon className="h-3.5 w-3.5 shrink-0" />
            {text}
          </div>
        ))}
        <div className="flex items-center gap-2 text-xs text-ink-faint">
          <Clock className="h-3.5 w-3.5 shrink-0" />
          This link expires — your HR team can send a fresh one at any time.
        </div>
      </div>
    </div>
  )
}
