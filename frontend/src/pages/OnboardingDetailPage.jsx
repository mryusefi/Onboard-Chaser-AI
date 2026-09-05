import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft, Loader2, AlertCircle, User, FileText, Clock, Bell,
} from 'lucide-react'
import ReminderHistory from '../components/ReminderHistory'
import { authFetch } from '../utils/api'

// US10 — placeholder onboarding detail view. Shows the candidate + progress
// data from the same list endpoint; US11 will attach document-level detail
// here (route: /admin/onboarding/:id).

const API_BASE = '/api/v1'

const STATUS_CHIP = {
  pending: 'bg-amber-100 text-amber-700',
  in_progress: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
}

export default function OnboardingDetailPage() {
  const { id } = useParams()
  const [item, setItem] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        // The list endpoint is the only aggregated source for now; find the row.
        const resp = await authFetch(`${API_BASE}/onboarding/?page=1&page_size=100`)
        const data = await resp.json()
        if (!resp.ok) throw new Error(data.detail || 'Failed to load onboarding')
        const found = (data.items || []).find((i) => i.onboarding_id === id)
        if (!found) throw new Error('Onboarding not found')
        if (!cancelled) setItem(found)
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [id])

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 py-10 px-4">
      <div className="max-w-3xl mx-auto">
        <Link
          to="/admin/onboarding"
          className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 mb-4"
        >
          <ArrowLeft className="w-4 h-4" /> Back to dashboard
        </Link>

        <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-8">
          {loading && (
            <div className="flex items-center gap-2 text-sm text-slate-500 py-6 justify-center">
              <Loader2 className="w-5 h-5 animate-spin" /> Loading onboarding…
            </div>
          )}

          {error && (
            <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" /> {error}
            </div>
          )}

          {item && (
            <>
              <h1 className="text-2xl font-bold text-slate-900 mb-1">
                {item.candidate.full_name}
              </h1>
              <p className="text-sm text-slate-500 mb-6">
                {item.candidate.email}
                {item.candidate.position ? ` · ${item.candidate.position}` : ''}
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
                <div className="bg-slate-50 rounded-xl p-4">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5 mb-1">
                    <User className="w-3.5 h-3.5" /> Status
                  </p>
                  <span
                    className={`text-xs font-semibold px-3 py-1 rounded-full capitalize ${
                      STATUS_CHIP[item.status] || 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {item.status.replace('_', ' ')}
                  </span>
                </div>
                <div className="bg-slate-50 rounded-xl p-4">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5 mb-1">
                    <Bell className="w-3.5 h-3.5" /> Invitation
                  </p>
                  <span className="text-sm font-medium text-slate-800 capitalize">
                    {item.invitation_email_status.replace('_', ' ')}
                  </span>
                </div>
                <div className="bg-slate-50 rounded-xl p-4">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5 mb-1">
                    <Clock className="w-3.5 h-3.5" /> Started
                  </p>
                  <span className="text-sm text-slate-700">
                    {item.started_at ? new Date(item.started_at).toLocaleString() : 'Not started yet'}
                  </span>
                </div>
                <div className="bg-slate-50 rounded-xl p-4">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5 mb-1">
                    <FileText className="w-3.5 h-3.5" /> Documents
                  </p>
                  <span className="text-sm text-slate-700">
                    {item.completed_documents} of {item.total_documents} submitted
                  </span>
                </div>
              </div>

              {/* Progress bar — same style as OnboardingPortal */}
              <div className="w-full bg-slate-100 rounded-full h-3 mb-2">
                <div
                  className={`h-3 rounded-full transition-all duration-700 ease-out ${
                    item.completion_percentage === 100
                      ? 'bg-green-500'
                      : item.completion_percentage >= 50
                      ? 'bg-primary-500'
                      : 'bg-amber-500'
                  }`}
                  style={{ width: `${item.completion_percentage}%` }}
                ></div>
              </div>
              <p className="text-sm text-slate-500 mb-6">{item.completion_percentage}% complete</p>

              {item.needs_attention && (
                <div className="mb-6 flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
                  <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                  This onboarding is flagged as needing attention (expired link, no
                  invitation, stalled progress, or blocked reminders).
                </div>
              )}

              {/* Reminder history (US08/US09 component) — also a natural
                  anchor for US11 to extend with document-level detail. */}
              <ReminderHistory onboardingId={item.onboarding_id} />

              <p className="mt-6 text-xs text-slate-400 border-t border-slate-100 pt-4">
                Placeholder view (US10). Document-level detail lands with US11.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
