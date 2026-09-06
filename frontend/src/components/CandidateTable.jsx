import { Link } from 'react-router-dom'
import { ChevronRight, AlertTriangle } from 'lucide-react'
import Badge from './ui/Badge'
import ProgressBar from './ui/ProgressBar'
import { formatDateShort, initials } from '../utils/format'

const AVATAR_COLORS = ['#0B6E6E', '#14213D', '#7C5C2B', '#5B5F6B', '#3D5A80']

function avatarColor(id) {
  let hash = 0
  const s = String(id)
  for (let i = 0; i < s.length; i++) hash = s.charCodeAt(i) + ((hash << 5) - hash)
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]
}

// US12-frontend: renders a real US10 list item (server shape mapped by
// OnboardingContext.mapServerItem). Adds the needs_attention badge and the
// invitation status column to the prototype's table.
export default function CandidateTable({ candidates, loading = false }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 rounded-2xl border border-border bg-surface py-16 text-sm text-ink-faint shadow-card">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand border-t-transparent" />
        Loading onboardings…
      </div>
    )
  }

  if (candidates.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-1.5 rounded-2xl border border-dashed border-border py-16 text-center">
        <p className="text-sm font-medium text-ink">No candidates match your filters</p>
        <p className="text-sm text-ink-faint">Try a different search term or status.</p>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface shadow-card">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="border-b border-border-soft bg-surface-sunken/50 text-xs font-medium uppercase tracking-wide text-ink-faint">
            <th className="px-5 py-3">Candidate</th>
            <th className="px-5 py-3">Position</th>
            <th className="px-5 py-3">Progress</th>
            <th className="px-5 py-3">Invitation</th>
            <th className="px-5 py-3">Status</th>
            <th className="px-5 py-3">Attention</th>
            <th className="px-5 py-3" />
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => (
            <tr
              key={c.id}
              className="group border-b border-border-soft last:border-0 hover:bg-surface-sunken/40"
            >
              <td className="px-5 py-3.5">
                <Link to={`/onboardings/${c.id}`} className="flex items-center gap-3">
                  <span
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold text-white"
                    style={{ backgroundColor: avatarColor(c.id) }}
                  >
                    {initials(c.name)}
                  </span>
                  <span>
                    <span className="block text-[13.5px] font-medium text-ink group-hover:text-brand-dark">{c.name}</span>
                    <span className="block text-xs text-ink-faint">{c.email}</span>
                  </span>
                </Link>
              </td>
              <td className="px-5 py-3.5 text-[13.5px] text-ink-soft">{c.position || '—'}</td>
              <td className="px-5 py-3.5">
                <div className="flex items-center gap-2.5">
                  <ProgressBar percent={c.progress.percent} size="sm" className="w-24" />
                  <span className="tabular font-mono text-xs text-ink-soft">{c.progress.percent}%</span>
                </div>
                <span className="text-[11px] text-ink-faint">
                  {c.progress.completed}/{c.progress.total} documents
                </span>
              </td>
              <td className="px-5 py-3.5">
                <Badge status={c.invitationEmailStatus} withIcon={false} />
              </td>
              <td className="px-5 py-3.5">
                <Badge status={c.status} />
              </td>
              <td className="px-5 py-3.5">
                {c.needsAttention ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-danger-soft px-2.5 py-1 text-xs font-medium text-danger">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    Needs attention
                  </span>
                ) : (
                  <span className="text-xs text-ink-faint">—</span>
                )}
              </td>
              <td className="px-5 py-3.5 text-right">
                <Link
                  to={`/onboardings/${c.id}`}
                  className="inline-flex items-center gap-1 text-[13px] font-medium text-ink-soft hover:text-brand-dark"
                >
                  View
                  <ChevronRight className="h-3.5 w-3.5" />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
