import { useState } from 'react'
import { CheckCircle2, Circle, FileText, AlertTriangle, Loader2, Undo2 } from 'lucide-react'
import Badge from './ui/Badge'
import { updateVerification } from '../api/client'
import { useToast } from '../context/ToastContext'

// US12-frontend: real Document shape from GET /onboarding/{id}/detail.
// variant "hr": HR detail page — status + verification chips, preview link,
//               Verify/Reject/Reset controls (manual HR verification, US11).
// variant "portal": candidate checklist — upload slot via children (FileUpload).

function VerificationControls({ doc, onVerified }) {
  const { showToast } = useToast()
  const [busy, setBusy] = useState(false)
  const [showNote, setShowNote] = useState(false)
  const [note, setNote] = useState('')

  async function setStatus(status) {
    setBusy(true)
    try {
      const updated = await updateVerification(doc.id, status, note.trim() || undefined)
      showToast(`Marked ${updated.verification_status}.`)
      onVerified?.(updated)
      setShowNote(false)
      setNote('')
    } catch (err) {
      showToast(err.message)
    } finally {
      setBusy(false)
    }
  }

  const canVerify = doc.status === 'uploaded' || doc.status === 'completed'

  return (
    <div className="flex flex-col items-end gap-2">
      <div className="flex items-center gap-1.5">
        {canVerify && doc.verification_status !== 'verified' && (
          <button
            onClick={() => setStatus('verified')}
            disabled={busy}
            className="flex items-center gap-1 rounded-lg bg-success-soft px-2.5 py-1.5 text-xs font-semibold text-success transition-colors hover:opacity-80 disabled:opacity-50"
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : '✓'} Verify
          </button>
        )}
        {canVerify && doc.verification_status !== 'rejected' && (
          <button
            onClick={() => setShowNote((v) => !v)}
            disabled={busy}
            className="flex items-center gap-1 rounded-lg bg-danger-soft px-2.5 py-1.5 text-xs font-semibold text-danger transition-colors hover:opacity-80 disabled:opacity-50"
          >
            ✕ Reject
          </button>
        )}
        {doc.verification_status !== 'unverified' && (
          <button
            onClick={() => setStatus('unverified')}
            disabled={busy}
            title="Reset verification"
            className="rounded-lg p-1.5 text-ink-faint hover:bg-surface-sunken hover:text-ink disabled:opacity-50"
          >
            <Undo2 className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      {showNote && (
        <div className="flex w-full items-center gap-2">
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Rejection reason (optional)…"
            className="h-9 flex-1 rounded-lg border border-border bg-surface px-3 text-[13px] text-ink focus:border-brand focus:outline-none"
          />
          <button
            onClick={() => setStatus('rejected')}
            disabled={busy}
            className="rounded-lg bg-danger px-3 py-2 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Confirm'}
          </button>
        </div>
      )}
    </div>
  )
}

export default function DocumentRow({ doc, variant = 'hr', onPreview, onVerified, children }) {
  const hasFile = !!doc.file_name
  const isDone = doc.status === 'uploaded' || doc.status === 'completed'

  if (variant === 'portal') {
    return (
      <div
        className={`rounded-xl border px-4 py-4 ${
          isDone ? 'border-success/20 bg-success-soft/40' : 'border-border bg-surface'
        }`}
      >
        <div className="flex items-start gap-3">
          {isDone ? (
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
          ) : (
            <Circle className="mt-0.5 h-5 w-5 shrink-0 text-ink-faint" />
          )}
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
              <p className="text-[14px] font-medium text-ink">{doc.name}</p>
              {doc.required ? (
                <span className="text-xs font-medium text-ink-faint">Required</span>
              ) : (
                <span className="text-xs font-medium text-ink-faint">Optional</span>
              )}
            </div>
            {hasFile ? (
              <p className="mt-0.5 flex items-center gap-1.5 text-xs text-ink-soft">
                <FileText className="h-3.5 w-3.5" />
                {doc.file_name} · Uploaded {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : '—'}
              </p>
            ) : (
              <p className="mt-0.5 text-[13px] text-ink-soft">{doc.instructions || 'Please upload this document.'}</p>
            )}
            {!isDone && children ? <div className="mt-3">{children}</div> : null}
          </div>
        </div>
      </div>
    )
  }

  // ── HR variant ─────────────────────────────────────────────────────────
  return (
    <div className="border-b border-border-soft px-1 py-4 last:border-0">
      <div className="flex items-start gap-3.5">
        {isDone ? (
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
        ) : doc.status === 'missing' ? (
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
        ) : (
          <Circle className="mt-0.5 h-5 w-5 shrink-0 text-ink-faint" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[14px] font-medium text-ink">{doc.name}</p>
            <Badge status={doc.status} withIcon={false} />
            <Badge status={doc.verification_status} withIcon={false} />
          </div>
          {hasFile ? (
            <button
              onClick={() => onPreview?.(doc)}
              className="mt-1 flex items-center gap-1.5 text-xs text-ink-soft underline decoration-border underline-offset-2 hover:text-brand-dark"
            >
              <FileText className="h-3.5 w-3.5" />
              {doc.file_name} · {doc.file_size ? `${Math.max(1, Math.round(parseInt(doc.file_size, 10) / 1024))} KB` : '—'} ·
              Uploaded {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : '—'}
            </button>
          ) : (
            <p className="mt-1 text-xs text-ink-faint">Not submitted</p>
          )}
          {doc.verification_note && (
            <p className="mt-1 text-xs italic text-ink-soft">“{doc.verification_note}”</p>
          )}
        </div>
        {canVerifyRow(doc) && (
          <VerificationControls doc={doc} onVerified={onVerified} />
        )}
      </div>
    </div>
  )
}

function canVerifyRow(doc) {
  return doc.status === 'uploaded' || doc.status === 'completed' || doc.verification_status !== 'unverified'
}
