import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Users, AlertTriangle, CheckCircle2, Clock, Plus } from 'lucide-react'
import Topbar from '../components/Topbar'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import CandidateTable from '../components/CandidateTable'
import { fetchOnboardings } from '../api/client'
import { useAuth } from '../context/AuthContext'

// US12-frontend: summary cards computed from the real US10 list endpoint
// (needs_attention flag drives the "Needs attention" count directly).

function SummaryCard({ label, value, Icon, tone, loading }) {
  const toneClasses = {
    brand: 'bg-brand-soft text-brand-dark',
    warning: 'bg-warning-soft text-warning',
    success: 'bg-success-soft text-success',
    danger: 'bg-danger-soft text-danger',
  }
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <p className="text-[13px] font-medium text-ink-soft">{label}</p>
        <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${toneClasses[tone]}`}>
          <Icon className="h-4 w-4" />
        </span>
      </div>
      {loading ? (
        <div className="mt-3 h-9 w-14 animate-pulse rounded-lg bg-surface-sunken" />
      ) : (
        <p className="mt-3 font-display text-3xl font-semibold tracking-tight text-ink">{value}</p>
      )}
    </Card>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [attentionRows, setAttentionRows] = useState([])
  const [completedRows, setCompletedRows] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        // One real list fetch for totals…
        const all = await fetchOnboardings({ page: 1, pageSize: 100 })
        if (cancelled) return
        setData(all)
        // …and two filtered fetches for the attention/completed cards
        // (needs_attention and completed are server-side filters, US10).
        const [att, comp] = await Promise.all([
          fetchOnboardings({ needsAttention: true, page: 1, pageSize: 5 }),
          fetchOnboardings({ status: 'completed', page: 1, pageSize: 5 }),
        ])
        if (cancelled) return
        setAttentionRows(att.items || [])
        setCompletedRows(comp.items || [])
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const items = data?.items || []
  const firstName = (user?.email || 'HR').split('@')[0]

  return (
    <div>
      <Topbar
        eyebrow="Dashboard"
        title={`Welcome back, ${firstName}`}
        subtitle="Overview of your active onboardings."
        actions={
          <Button as={Link} to="/create-onboarding" icon={Plus}>
            New onboarding
          </Button>
        }
      />

      <div className="px-8 py-7">
        {error && (
          <div className="mb-4 rounded-xl border border-danger/25 bg-danger-soft px-4 py-3 text-sm text-danger">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <SummaryCard label="Active onboardings" value={data?.total ?? 0} Icon={Users} tone="brand" loading={loading} />
          <SummaryCard
            label="Needs attention"
            value={loading ? null : attentionRows.length}
            Icon={AlertTriangle}
            tone="warning"
            loading={loading}
          />
          <SummaryCard
            label="Completed"
            value={loading ? null : completedRows.length}
            Icon={CheckCircle2}
            tone="success"
            loading={loading}
          />
          <SummaryCard
            label="Pending start"
            value={loading ? null : items.filter((i) => i.status === 'pending').length}
            Icon={Clock}
            tone="brand"
            loading={loading}
          />
        </div>

        <div className="mt-8">
          <div className="mb-3.5 flex items-center justify-between">
            <h2 className="font-display text-base font-semibold text-ink">Onboardings</h2>
            <Link to="/onboardings" className="text-[13px] font-medium text-brand-dark hover:underline">
              View all
            </Link>
          </div>
          <CandidateTable candidates={items.slice(0, 5)} loading={loading} />
          {attentionRows.length > 0 && (
            <p className="mt-3 flex items-center gap-1.5 text-[13px] text-warning">
              <AlertTriangle className="h-3.5 w-3.5" />
              {attentionRows.length} onboarding{attentionRows.length === 1 ? '' : 's'} need
              {attentionRows.length === 1 ? 's' : ''} attention right now.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
