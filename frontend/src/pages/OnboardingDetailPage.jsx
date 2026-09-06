import { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft, Loader2, AlertCircle, User, FileText, Clock, Bell,
  Eye, Download, CheckCircle2, XCircle, Undo2, Inbox,
} from 'lucide-react'
import ReminderHistory from '../components/ReminderHistory'
import { authFetch } from '../utils/api'

// US11 — Candidate detail & document verification (completes the US10
// placeholder at /admin/onboarding/:id).
// Verification here is MANUAL HR verification: HR previews/downloads the
// document via a short-lived access URL and marks it verified/rejected.
// AI-assisted verification is US12 (out of MVP scope).

const API_BASE = '/api/v1'

// Reuse the same chip language as the dashboard/portal (US10 pattern).
const STATUS_CHIP = {
  pending: 'bg-amber-100 text-amber-700',
  in_progress: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  uploaded: 'bg-emerald-100 text-emerald-700',
  missing: 'bg-red-100 text-red-700',
}

// New colors for the verification states (same chip component pattern).
const VERIFICATION_CHIP = {
  unverified: 'bg-slate-100 text-slate-600',
  verified: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
}

const INVITATION_CHIP = {
  not_sent: 'bg-slate-100 text-slate-600',
  sent: 'bg-blue-100 text-blue-700',
  failed: 'bg-red-100 text-red-700',
  delivered: 'bg-green-100 text-green-700',
  bounced: 'bg-orange-100 text-orange-700',
}

function formatBytes(size) {
  if (!size) return '—'
  const n = parseInt(size, 10)
  if (Number.isNaN(n)) return size
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

function isPreviewable(mime) {
  return !!mime && (mime.startsWith('image/') || mime === 'application/pdf')
}

function Chip({ kind, value, label }) {
  const palette = kind === 'verification' ? VERIFICATION_CHIP : STATUS_CHIP
  return (
    <span className={`text-xs font-semibold px-3 py-1 rounded-full capitalize ${palette[value] || 'bg-slate-100 text-slate-600'}`}>
      {label || value.replace(/_/g, ' ')}
    </span>
  )
}

// One document row: preview/download + verification controls with their own
// per-row loading/success/error state.
function DocumentRow({ doc, onChanged }) {
  const [busy, setBusy] = useState(false) // preview / download fetch
  const [verifying, setVerifying] = useState(false)
  const [rowError, setRowError] = useState(null)
  const [note, setNote] = useState('')
  const [showNote, setShowNote] = useState(false)
  const [preview, setPreview] = useState(null) // { url, mime, name }

  const hasFile = !!doc.file_name

  const fetchAccessUrl = async () => {
    // Fetch a FRESH short-lived URL every time — never reuse/cache one past
    // its expiry (access-url endpoint returns a 10-minute signed URL).
    const resp = await authFetch(`${API_BASE}/documents/${doc.id}/access-url`)
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.detail || 'Failed to get access URL')
    return data
  }

  const openPreview = async () => {
    setBusy(true)
    setRowError(null)
    try {
      const data = await fetchAccessUrl()
      // Inline preview: PDF in an <iframe>, image in an <img> (modal below).
      setPreview({ url: data.access_url, mime: data.file_mime_type, name: data.file_name })
    } catch (err) {
      setRowError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const download = async () => {
    setBusy(true)
    setRowError(null)
    try {
      const data = await fetchAccessUrl()
      // Trigger a download via a hidden anchor (fresh URL, no caching).
      const a = document.createElement('a')
      a.href = data.access_url
      a.download = data.file_name || 'document'
      document.body.appendChild(a)
      a.click()
      a.remove()
    } catch (err) {
      setRowError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const setVerification = async (status) => {
    setVerifying(true)
    setRowError(null)
    try {
      const resp = await authFetch(`${API_BASE}/documents/${doc.id}/verification`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          verification_status: status,
          ...(status === 'rejected' && note.trim() ? { verification_note: note.trim() } : {}),
        }),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.detail || 'Failed to update verification')
      setShowNote(false)
      setNote('')
      onChanged(data)
    } catch (err) {
      setRowError(err.message)
    } finally {
      setVerifying(false)
    }
  }

  const canVerify = doc.status === 'uploaded' || doc.status === 'completed'

  return (
    <div className="border border-slate-200 rounded-xl p-4 hover:border-primary-300 transition-colors">
      <div className="flex flex-wrap items-start gap-3">
        <div className="flex-1 min-w-[200px]">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold text-slate-900">{doc.name}</h3>
            {doc.required ? (
              <span className="text-[10px] font-bold uppercase tracking-wider bg-red-50 text-red-600 px-1.5 py-0.5 rounded">Required</span>
            ) : (
              <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">Optional</span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            <Chip kind="status" value={doc.status} />
            <Chip kind="verification" value={doc.verification_status} />
          </div>
          {hasFile && (
            <p className="text-xs text-slate-500 mt-2">
              {doc.file_name} · {formatBytes(doc.file_size)}
              {doc.uploaded_at && ` · uploaded ${new Date(doc.uploaded_at).toLocaleString()}`}
            </p>
          )}
          {doc.verification_note && (
            <p className="text-xs text-slate-600 mt-1 italic">“{doc.verification_note}”</p>
          )}
        </div>

        {/* Preview / Download / Verify controls */}
        <div className="flex flex-col items-end gap-2">
          <div className="flex items-center gap-2">
            {hasFile && isPreviewable(doc.file_mime_type) && (
              <button
                onClick={openPreview}
                disabled={busy}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 disabled:opacity-50 transition-colors"
              >
                {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Eye className="w-3.5 h-3.5" />} Preview
              </button>
            )}
            {hasFile && (
              <button
                onClick={download}
                disabled={busy}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50 transition-colors"
              >
                {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} Download
              </button>
            )}
            {!hasFile && <span className="text-xs text-slate-400">No file uploaded yet</span>}
          </div>

          {canVerify && (
            <div className="flex items-center gap-2">
              {doc.verification_status !== 'verified' && (
                <button
                  onClick={() => setVerification('verified')}
                  disabled={verifying}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-green-700 bg-green-50 hover:bg-green-100 disabled:opacity-50 transition-colors"
                >
                  {verifying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />} Verify
                </button>
              )}
              {doc.verification_status !== 'rejected' && (
                <button
                  onClick={() => setShowNote((v) => !v)}
                  disabled={verifying}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-red-700 bg-red-50 hover:bg-red-100 disabled:opacity-50 transition-colors"
                >
                  <XCircle className="w-3.5 h-3.5" /> Reject
                </button>
              )}
              {doc.verification_status !== 'unverified' && (
                <button
                  onClick={() => setVerification('unverified')}
                  disabled={verifying}
                  title="Reset verification"
                  className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 disabled:opacity-50 transition-colors"
                >
                  <Undo2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Rejection note input */}
      {showNote && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Rejection reason (optional)…"
            className="flex-1 min-w-[200px] px-3 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <button
            onClick={() => setVerification('rejected')}
            disabled={verifying}
            className="px-3 py-2 rounded-xl text-xs font-semibold text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 transition-colors"
          >
            {verifying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Confirm rejection'}
          </button>
        </div>
      )}

      {rowError && (
        <div className="mt-3 flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" /> {rowError}
        </div>
      )}

      {/* Inline preview modal: PDF via <iframe>, image via <img> */}
      {preview && (
        <div
          className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
          onClick={() => setPreview(null)}
        >
          <div
            className="bg-white rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200">
              <p className="font-semibold text-slate-900 text-sm">{preview.name}</p>
              <button
                onClick={() => setPreview(null)}
                className="text-sm text-slate-500 hover:text-slate-900 px-2"
              >
                Close
              </button>
            </div>
            <div className="flex-1 overflow-auto bg-slate-50 min-h-[300px] flex items-center justify-center">
              {preview.mime === 'application/pdf' ? (
                <iframe
                  src={preview.url}
                  title={preview.name}
                  className="w-full h-[70vh]"
                />
              ) : (
                <img src={preview.url} alt={preview.name} className="max-w-full max-h-[70vh] object-contain" />
              )}
            </div>
            <p className="px-5 py-2 text-xs text-slate-400">
              Access URL is short-lived ({`~10`}&nbsp;min). Fetch a fresh one for the next preview/download.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

export default function OnboardingDetailPage() {
  const { id } = useParams()
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await authFetch(`${API_BASE}/onboarding/${id}/detail`)
      const data = await resp.json()
      if (!resp.ok) {
        throw new Error(resp.status === 404 ? 'Onboarding not found' : data.detail || 'Failed to load onboarding')
      }
      setDetail(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  const applyVerificationUpdate = (updated) => {
    setDetail((prev) => ({
      ...prev,
      documents: prev.documents.map((d) =>
        d.id === updated.id
          ? {
              ...d,
              verification_status: updated.verification_status,
              verification_note: updated.verification_note,
              verified_at: updated.verified_at,
              verified_by: updated.verified_by,
            }
          : d
      ),
    }))
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 py-10 px-4">
      <div className="max-w-4xl mx-auto">
        <Link
          to="/admin/onboarding"
          className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 mb-4"
        >
          <ArrowLeft className="w-4 h-4" /> Back to dashboard
        </Link>

        <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-8">
          {loading && (
            <div className="flex items-center justify-center gap-2 text-sm text-slate-500 py-10">
              <Loader2 className="w-5 h-5 animate-spin" /> Loading onboarding…
            </div>
          )}

          {error && (
            <div className="py-10 text-center">
              <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
              <p className="text-slate-900 font-semibold">{error}</p>
              <p className="text-sm text-slate-500 mt-1">
                {error.includes('not found')
                  ? 'It may have been removed, or the link is out of date.'
                  : 'Check your HR token (localStorage.hr_token) and try again.'}
              </p>
              <Link
                to="/admin/onboarding"
                className="inline-block mt-4 px-4 py-2 rounded-xl text-sm font-semibold text-white bg-primary-600 hover:bg-primary-700"
              >
                Back to dashboard
              </Link>
            </div>
          )}

          {detail && (
            <>
              {/* ── Candidate header ─────────────────────────────────── */}
              <h1 className="text-2xl font-bold text-slate-900">{detail.candidate.full_name}</h1>
              <p className="text-sm text-slate-500">
                {detail.candidate.email}
                {detail.candidate.phone ? ` · ${detail.candidate.phone}` : ''}
                {detail.candidate.position ? ` · ${detail.candidate.position}` : ''}
              </p>

              <div className="flex flex-wrap items-center gap-2 mt-3 mb-6">
                <Chip kind="status" value={detail.status} />
                <span className={`text-xs font-semibold px-3 py-1 rounded-full capitalize ${INVITATION_CHIP[detail.invitation_email_status] || INVITATION_CHIP.not_sent}`}>
                  Invitation: {detail.invitation_email_status.replace(/_/g, ' ')}
                </span>
                <span className="text-xs text-slate-400 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {detail.started_at
                    ? `started ${new Date(detail.started_at).toLocaleString()}`
                    : 'not started yet'}
                  {detail.completed_at
                    ? ` · completed ${new Date(detail.completed_at).toLocaleString()}`
                    : ''}
                </span>
              </div>

              {/* ── Documents ────────────────────────────────────────── */}
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-primary-600" /> Documents
                </h2>
                <span className="text-xs text-slate-400">
                  {detail.documents.filter((d) => d.file_name).length}/{detail.documents.length} uploaded ·
                  manual HR verification
                </span>
              </div>

              {detail.documents.length === 0 ? (
                <div className="py-8 text-center border border-dashed border-slate-200 rounded-xl">
                  <Inbox className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                  <p className="text-sm text-slate-500">No documents requested for this onboarding.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {detail.documents.map((doc) => (
                    <DocumentRow
                      key={doc.id}
                      doc={doc}
                      onChanged={applyVerificationUpdate}
                    />
                  ))}
                </div>
              )}

              {/* ── Reminder history (kept from US10) ────────────────── */}
              <div className="mt-6">
                <ReminderHistory onboardingId={detail.onboarding_id} />
              </div>

              <p className="mt-6 text-xs text-slate-400 border-t border-slate-100 pt-4">
                Document verification is manual (HR-driven). AI-assisted verification is US12
                and remains out of scope for this MVP.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
