import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  LayoutDashboard, Loader2, AlertCircle, Search, AlertTriangle,
  ChevronLeft, ChevronRight, Inbox, Eye,
} from 'lucide-react'
import AdminNav from '../components/AdminNav'
import { authFetch } from '../utils/api'

// US10 — HR dashboard: all onboardings at a glance.
// Status chips reuse the color language of OnboardingPortal's STATUS_CONFIG;
// the progress bar mirrors OnboardingPortal's Progress Card styling.

const API_BASE = '/api/v1'

// Color-coded chips (same palette as the candidate portal document statuses).
const STATUS_CHIP = {
  pending: 'bg-amber-100 text-amber-700',
  in_progress: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
}

const INVITATION_CHIP = {
  not_sent: 'bg-slate-100 text-slate-600',
  sent: 'bg-blue-100 text-blue-700',
  failed: 'bg-red-100 text-red-700',
  delivered: 'bg-green-100 text-green-700',
  bounced: 'bg-orange-100 text-orange-700',
}

function ProgressBar({ percent }) {
  // Same style/colors as OnboardingPortal's Progress Card bar.
  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="w-full bg-slate-100 rounded-full h-2.5">
        <div
          className={`h-2.5 rounded-full transition-all duration-500 ${
            percent === 100 ? 'bg-green-500' : percent >= 50 ? 'bg-primary-500' : 'bg-amber-500'
          }`}
          style={{ width: `${percent}%` }}
        ></div>
      </div>
      <span className="text-xs font-semibold text-slate-600 w-9 text-right">{percent}%</span>
    </div>
  )
}

export default function OnboardingDashboardPage() {
  const [rows, setRows] = useState(null) // null = loading
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(10)
  const [status, setStatus] = useState('')
  const [attentionOnly, setAttentionOnly] = useState(false)
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const debounceRef = useRef(null)

  // Debounce the search box (400ms) before hitting the backend.
  const onSearchChange = (e) => {
    const value = e.target.value
    setSearchInput(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setSearch(value)
      setPage(1)
    }, 400)
  }

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (status) params.set('status', status)
      if (attentionOnly) params.set('needs_attention', 'true')
      if (search.trim()) params.set('search', search.trim())
      params.set('page', String(page))
      params.set('page_size', String(pageSize))
      const resp = await authFetch(`${API_BASE}/onboarding/?${params.toString()}`)
      if (resp.status === 401) {
        throw new Error('Not authorized — set your HR token (localStorage.hr_token).')
      }
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.detail || 'Failed to load onboardings')
      setRows(data.items)
      setTotal(data.total)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [status, attentionOnly, search, page, pageSize])

  useEffect(() => {
    load()
  }, [load])

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 py-10 px-4">
      <div className="max-w-6xl mx-auto">
        <AdminNav />

        <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-6">
          <div className="flex items-center gap-3 mb-1">
            <LayoutDashboard className="w-6 h-6 text-primary-600" />
            <h1 className="text-2xl font-bold text-slate-900">Onboarding Dashboard</h1>
          </div>
          <p className="text-sm text-slate-500 mb-5">
            Track every candidate's progress and spot who needs a personal follow-up.
          </p>

          {/* ── Filters ─────────────────────────────────────────────── */}
          <div className="flex flex-wrap items-center gap-3 mb-5">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                value={searchInput}
                onChange={onSearchChange}
                placeholder="Search by candidate name or email…"
                className="w-full pl-9 pr-3 py-2 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <select
              value={status}
              onChange={(e) => { setStatus(e.target.value); setPage(1) }}
              className="px-3 py-2 rounded-xl border border-slate-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="in_progress">In progress</option>
              <option value="completed">Completed</option>
            </select>

            <label className="flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200 cursor-pointer hover:bg-slate-50 text-sm">
              <input
                type="checkbox"
                checked={attentionOnly}
                onChange={(e) => { setAttentionOnly(e.target.checked); setPage(1) }}
                className="w-4 h-4 accent-primary-600"
              />
              <span className="font-medium text-slate-700">Needs attention only</span>
            </label>
          </div>

          {/* ── States ──────────────────────────────────────────────── */}
          {error && (
            <div className="mb-4 flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" /> {error}
            </div>
          )}

          {loading && !rows && (
            <div className="flex items-center gap-2 text-sm text-slate-500 py-8 justify-center">
              <Loader2 className="w-5 h-5 animate-spin" /> Loading onboardings…
            </div>
          )}

          {!loading && !error && rows && rows.length === 0 && (
            <div className="py-12 text-center">
              <Inbox className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-600 font-medium">No onboardings found</p>
              <p className="text-sm text-slate-500 mt-1">
                {search || status || attentionOnly
                  ? 'Try clearing the filters.'
                  : 'Create your first onboarding from the "New Onboarding" page.'}
              </p>
            </div>
          )}

          {/* ── Table ───────────────────────────────────────────────── */}
          {!loading && !error && rows && rows.length > 0 && (
            <>
              <div className="overflow-x-auto rounded-xl border border-slate-200">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                      <th className="px-4 py-3">Candidate</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3">Progress</th>
                      <th className="px-4 py-3">Invitation</th>
                      <th className="px-4 py-3">Attention</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {loading ? (
                      <tr>
                        <td colSpan="6" className="px-4 py-8 text-center text-slate-500">
                          <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> Updating…
                        </td>
                      </tr>
                    ) : (
                      rows.map((item) => (
                        <tr key={item.onboarding_id} className="hover:bg-slate-50 transition-colors">
                          <td className="px-4 py-3">
                            <p className="font-medium text-slate-900">{item.candidate.full_name}</p>
                            <p className="text-xs text-slate-500">{item.candidate.email}</p>
                            {item.candidate.position && (
                              <p className="text-xs text-slate-400">{item.candidate.position}</p>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`text-xs font-semibold px-3 py-1 rounded-full capitalize ${
                                STATUS_CHIP[item.status] || 'bg-slate-100 text-slate-600'
                              }`}
                            >
                              {item.status.replace('_', ' ')}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <ProgressBar percent={item.completion_percentage} />
                            <p className="text-xs text-slate-400 mt-1">
                              {item.completed_documents}/{item.total_documents} documents
                            </p>
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`text-xs font-semibold px-3 py-1 rounded-full capitalize ${
                                INVITATION_CHIP[item.invitation_email_status] || INVITATION_CHIP.not_sent
                              }`}
                            >
                              {item.invitation_email_status.replace('_', ' ')}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            {item.needs_attention ? (
                              <span className="inline-flex items-center gap-1 text-xs font-semibold px-3 py-1 rounded-full bg-red-100 text-red-700">
                                <AlertTriangle className="w-3 h-3" /> Needs attention
                              </span>
                            ) : (
                              <span className="text-xs text-slate-400">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <Link
                              to={`/admin/onboarding/${item.onboarding_id}`}
                              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-primary-700 bg-primary-50 hover:bg-primary-100 transition-colors"
                            >
                              <Eye className="w-3.5 h-3.5" /> View
                            </Link>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* ── Pagination ──────────────────────────────────────── */}
              <div className="flex items-center justify-between mt-4 text-sm">
                <p className="text-slate-500">
                  {total} onboarding{total !== 1 ? 's' : ''} · page {page} of {totalPages}
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1 || loading}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    <ChevronLeft className="w-4 h-4" /> Prev
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages || loading}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    Next <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
