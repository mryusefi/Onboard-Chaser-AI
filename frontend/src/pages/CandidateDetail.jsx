import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import {
  ArrowLeft, Download, FileText, Loader2,
} from 'lucide-react'
import Topbar from '../components/Topbar'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import ProgressBar from '../components/ui/ProgressBar'
import Modal from '../components/ui/Modal'
import DocumentRow from '../components/DocumentRow'
import ChaseTrail from '../components/ChaseTrail'
import { fetchOnboardingDetail, fetchAccessUrl, fetchReminderHistory } from '../api/client'
import { useToast } from '../context/ToastContext'
import { formatDate, formatDateTime } from '../utils/format'

// US12-frontend: powered by GET /onboarding/{id}/detail (US11) +
// /documents/{id}/access-url for preview/download + PATCH verification +
// /onboarding/{id}/reminders rendered through the kit's ChaseTrail.
// Verification controls live inside DocumentRow (single implementation);
// this page only wires onPreview/onDownload/onVerified.

export default function CandidateDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { showToast } = useToast()

  const [detail, setDetail] = useState(null)
  const [reminders, setReminders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [previewDoc, setPreviewDoc] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [previewMime, setPreviewMime] = useState(null)
  const [previewBusy, setPreviewBusy] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [detailData, reminderData] = await Promise.all([
        fetchOnboardingDetail(id),
        fetchReminderHistory(id).catch(() => []), // history is non-critical
      ])
      setDetail(detailData)
      setReminders(reminderData || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  async function openPreview(doc) {
    setPreviewDoc(doc)
    setPreviewUrl(null)
    setPreviewMime(doc.file_mime_type)
    setPreviewBusy(true)
    try {
      // Fresh short-lived URL per preview — never reuse past expiry.
      const data = await fetchAccessUrl(doc.id)
      setPreviewUrl(data.access_url)
    } catch (err) {
      showToast(err.message)
      setPreviewDoc(null)
    } finally {
      setPreviewBusy(false)
    }
  }

  async function handleDownload(doc) {
    try {
      const data = await fetchAccessUrl(doc.id)
      const a = document.createElement('a')
      a.href = data.access_url
      a.download = data.file_name || 'document'
      document.body.appendChild(a)
      a.click()
      a.remove()
    } catch (err) {
      showToast(err.message)
    }
  }

  function applyVerificationUpdate(updated) {
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

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-24 text-sm text-ink-faint">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading candidate…
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-8 py-16 text-center">
        <p className="text-sm font-medium text-ink">{error}</p>
        <p className="mt-1 text-sm text-ink-faint">
          Check your session and try again, or return to the list.
        </p>
        <Link to="/onboardings" className="mt-3 inline-block text-sm font-medium text-brand-dark hover:underline">
          Back to onboardings
        </Link>
      </div>
    )
  }

  if (!detail) return null

  const { candidate, documents } = detail
  const completed = documents.filter((d) => d.status === 'uploaded' || d.status === 'completed').length
  const percent = documents.length ? Math.round((completed / documents.length) * 100) : 0
  const firstName = candidate.full_name.split(' ')[0]

  return (
    <div className="pb-16">
      <div className="border-b border-border-soft px-8 py-6">
        <button
          onClick={() => navigate('/onboardings')}
          className="mb-4 flex items-center gap-1.5 text-[13px] font-medium text-ink-soft hover:text-ink"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to onboardings
        </button>

        <div className="flex flex-wrap items-start justify-between gap-6">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="font-display text-2xl font-semibold tracking-tight text-ink">{candidate.full_name}</h1>
              <Badge status={detail.status} />
            </div>
            <p className="mt-1 text-sm text-ink-soft">
              {candidate.email}
              {candidate.phone ? ` · ${candidate.phone}` : ''}
            </p>
            <p className="mt-0.5 text-sm text-ink-faint">{candidate.position}</p>
            <div className="mt-2.5 flex flex-wrap items-center gap-2">
              <Badge status={detail.invitation_email_status} withIcon={false}>
                Invitation: {detail.invitation_email_status.replace(/_/g, ' ')}
              </Badge>
              <span className="text-xs text-ink-faint">
                {detail.started_at
                  ? `Started ${formatDateTime(detail.started_at)}`
                  : 'Not started yet'}
                {detail.completed_at ? ` · Completed ${formatDateTime(detail.completed_at)}` : ''}
              </span>
            </div>
          </div>
        </div>

        <div className="mt-6 max-w-md">
          <div className="mb-1.5 flex items-center justify-between text-[13px]">
            <span className="font-medium text-ink">Progress</span>
            <span className="tabular font-mono text-ink-soft">{percent}%</span>
          </div>
          <ProgressBar percent={percent} size="lg" />
          <p className="mt-1.5 text-xs text-ink-faint">
            {completed} of {documents.length} documents submitted
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 px-8 py-7 lg:grid-cols-[1.6fr_1fr]">
        <Card className="p-6">
          <h2 className="font-display text-base font-semibold text-ink">Required documents</h2>
          <p className="mt-0.5 text-xs text-ink-faint">
            Verification is manual (HR review). AI verification is US12 — out of scope.
          </p>
          <div className="mt-3">
            {documents.map((doc) => (
              <DocumentRow
                key={doc.id}
                doc={doc}
                variant="hr"
                onPreview={openPreview}
                onVerified={applyVerificationUpdate}
              />
            ))}
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="font-display text-base font-semibold text-ink">Reminder activity</h2>
          <p className="mt-1 text-xs text-ink-faint">
            Automated follow-ups from the hourly scan plus manual sends.
          </p>
          <div className="mt-5">
            {reminders.length === 0 ? (
              <p className="text-sm text-ink-faint">No reminders sent yet.</p>
            ) : (
              <ChaseTrail
                items={[...reminders].reverse().map((r) => ({
                  id: r.id,
                  label:
                    r.reminder_type === 'expiry_warning' ? 'Expiry warning' : 'Midway reminder',
                  sublabel:
                    r.status === 'skipped' && r.reason
                      ? `Skipped — ${r.reason}`
                      : r.status === 'failed' && r.reason
                      ? `Failed — ${r.reason}`
                      : r.status === 'sent'
                      ? 'Email sent'
                      : r.status,
                  date: r.sent_at ? formatDateTime(r.sent_at) : '—',
                  status: r.status === 'sent' ? 'sent' : 'scheduled',
                }))}
              />
            )}
          </div>
        </Card>
      </div>

      {/* Preview modal: PDF in an iframe, image in an img — URL fetched fresh */}
      <Modal
        open={Boolean(previewDoc)}
        onClose={() => {
          setPreviewDoc(null)
          setPreviewUrl(null)
        }}
        title={previewDoc ? `Preview — ${previewDoc.name}` : 'Document preview'}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setPreviewDoc(null)}>
              Close
            </Button>
            <Button
              icon={Download}
              disabled={!previewUrl}
              onClick={() => previewDoc && handleDownload(previewDoc)}
            >
              Download
            </Button>
          </>
        }
      >
        {previewDoc && (
          <div>
            {previewBusy && (
              <div className="flex h-48 items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-surface-sunken/50 text-sm text-ink-faint">
                <Loader2 className="h-4 w-4 animate-spin" /> Requesting secure access URL…
              </div>
            )}
            {!previewBusy && previewUrl && previewMime === 'application/pdf' && (
              <iframe src={previewUrl} title={previewDoc.name} className="h-[60vh] w-full rounded-xl border border-border" />
            )}
            {!previewBusy && previewUrl && previewMime !== 'application/pdf' && (
              <div className="flex justify-center rounded-xl border border-border bg-surface-sunken/40 p-3">
                <img src={previewUrl} alt={previewDoc.name} className="max-h-[60vh] rounded-lg object-contain" />
              </div>
            )}
            {!previewBusy && !previewUrl && (
              <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-border bg-surface-sunken/50">
                <div className="flex flex-col items-center gap-2 text-ink-faint">
                  <FileText className="h-9 w-9" />
                  <span className="text-xs font-medium">URL not available</span>
                </div>
              </div>
            )}
            <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2.5 text-[13px]">
              <dt className="text-ink-faint">File</dt>
              <dd className="text-right text-ink-soft">{previewDoc.file_name}</dd>
              <dt className="text-ink-faint">Uploaded</dt>
              <dd className="text-right text-ink-soft">{formatDate(previewDoc.uploaded_at)}</dd>
              <dt className="text-ink-faint">Verification</dt>
              <dd className="text-right">
                <Badge status={previewDoc.verification_status} withIcon={false} />
              </dd>
            </dl>
            <p className="mt-3 text-xs text-ink-faint">
              The access URL is short-lived (~10 min) — a fresh one is fetched for each
              preview or download.
            </p>
          </div>
        )}
      </Modal>
    </div>
  )
}
