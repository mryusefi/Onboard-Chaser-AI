import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Plus } from 'lucide-react'
import Topbar from '../components/Topbar'
import Button from '../components/ui/Button'
import CandidateTable from '../components/CandidateTable'
import { useOnboarding } from '../context/OnboardingContext'

// US12-frontend: real backend filters. Status filter + needs_attention
// toggle + debounced search hit GET /api/v1/onboarding/ query params
// (server-side filtering, unlike the prototype's client-side filter).

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'in_progress', label: 'In progress' },
  { key: 'pending', label: 'Pending' },
  { key: 'completed', label: 'Completed' },
]

export default function Onboardings() {
  const { candidates, loading, error, meta, load, filters, setFilters } = useOnboarding()
  const [query, setQuery] = useState('')
  const debounceTimer = useRef(null)

  // Debounce the search box: 400 ms before triggering a server fetch.
  function handleSearch(e) {
    const value = e.target.value
    setQuery(value)
    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(() => {
      load({ query: value, page: 1 })
    }, 400)
  }

  useEffect(() => () => clearTimeout(debounceTimer.current), [])

  function handleFilter(key) {
    setFilters({ ...filters, status: key })
    load({ status: key, page: 1 })
  }

  function toggleAttention() {
    const next = !filters.attentionOnly
    setFilters({ ...filters, attentionOnly: next })
    load({ attentionOnly: next, page: 1 })
  }

  const totalPages = Math.max(1, Math.ceil(meta.total / meta.pageSize))

  return (
    <div>
      <Topbar
        eyebrow="Onboardings"
        title="All onboardings"
        subtitle={`${meta.total} candidate${meta.total === 1 ? '' : 's'} in the pipeline`}
        actions={
          <Button as={Link} to="/create-onboarding" icon={Plus}>
            New onboarding
          </Button>
        }
      />

      <div className="px-8 py-7">
        <div className="mb-5 flex flex-wrap items-center gap-3">
          <div className="relative w-full max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
            <input
              type="text"
              value={query}
              onChange={handleSearch}
              placeholder="Search by name or email"
              className="h-10 w-full rounded-lg border border-border bg-surface pl-9 pr-3 text-[13.5px] text-ink placeholder:text-ink-faint focus:border-brand"
            />
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                onClick={() => handleFilter(f.key)}
                className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors ${
                  filters.status === f.key
                    ? 'bg-ink text-white'
                    : 'bg-surface-sunken text-ink-soft hover:bg-border-soft'
                }`}
              >
                {f.label}
              </button>
            ))}
            <button
              onClick={toggleAttention}
              className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors ${
                filters.attentionOnly
                  ? 'bg-danger text-white'
                  : 'bg-surface-sunken text-ink-soft hover:bg-border-soft'
              }`}
            >
              Needs attention
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-xl border border-danger/25 bg-danger-soft px-4 py-3 text-sm text-danger">
            {error}
          </div>
        )}

        <CandidateTable candidates={candidates} loading={loading} />

        {/* Pagination (server-side, US10 offset/limit) */}
        {meta.total > meta.pageSize && (
          <div className="mt-4 flex items-center justify-between text-sm">
            <p className="text-ink-soft">
              Page {meta.page} of {totalPages} · {meta.total} total
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={meta.page <= 1 || loading}
                onClick={() => load({ page: meta.page - 1 })}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={meta.page >= totalPages || loading}
                onClick={() => load({ page: meta.page + 1 })}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
