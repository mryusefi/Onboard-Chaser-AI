// US12-frontend — OnboardingContext: the single data layer for the HR app.
// Every action calls the real backend (previously in-memory mock data);
// the Context API keeps the same action names as the prototype
// (candidates/getCandidate/sendReminder/sendInvitation/uploadDocument/
// createOnboarding) so the prepared UI's pages need minimal changes.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import {
  apiFetch,
  fetchOnboardings,
  createFullOnboarding,
  sendInvitation as apiSendInvitation,
} from '../api/client'
import { useToast } from './ToastContext'

const OnboardingContext = createContext(null)

// Server item (US10 shape) → the shape the prepared UI's components expect
// (mock-era fields kept: id/name/position/progress/status/lastActivity).
function mapServerItem(item) {
  const statusValue =
    typeof item.status === 'string' ? item.status : String(item.status)
  return {
    id: item.onboarding_id,
    name: item.candidate?.full_name || '—',
    email: item.candidate?.email || '',
    position: item.candidate?.position || '',
    progress: {
      completed: item.completed_documents ?? 0,
      total: item.total_documents ?? 0,
      percent: item.completion_percentage ?? 0,
    },
    status: statusValue, // pending | in_progress | completed (raw)
    needsAttention: !!item.needs_attention,
    invitationEmailStatus: item.invitation_email_status || 'not_sent',
    startedAt: item.started_at || null,
    completedAt: item.completed_at || null,
    lastActivity: item.started_at
      ? new Date(item.started_at).toLocaleDateString()
      : 'Not started',
  }
}

export function OnboardingProvider({ children }) {
  const [candidates, setCandidates] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [meta, setMeta] = useState({ total: 0, page: 1, pageSize: 20 })
  const [filters, setFilters] = useState({ query: '', status: 'all', attentionOnly: false })
  const { showToast } = useToast()

  const load = useCallback(
    async (override = {}) => {
      const f = { ...filters, ...override }
      setLoading(true)
      setError(null)
      try {
        const data = await fetchOnboardings({
          status: f.status !== 'all' ? f.status : undefined,
          needsAttention: f.attentionOnly ? true : undefined,
          search: f.query,
          page: override.page || meta.page,
          pageSize: meta.pageSize,
        })
        setCandidates(data.items.map(mapServerItem))
        setMeta({ total: data.total, page: data.page, pageSize: data.page_size })
      } catch (err) {
        setError(err.message)
        setCandidates([])
      } finally {
        setFilters(f)
        setLoading(false)
      }
    },
    [filters, meta.page, meta.pageSize, showToast]
  )

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Actions (same names as the prototype context) ──────────────────────
  const createOnboarding = useCallback(
    async (form) => {
      // US06 create-full: candidate + onboarding + seeded default documents.
      const result = await createFullOnboarding({ candidate: form.candidate })
      showToast('Onboarding created successfully.')
      return result
    },
    [showToast]
  )

  const sendInvitation = useCallback(
    async (onboardingId) => {
      // US07: renders + sends the invitation email (Resend, graceful fallback).
      const result = await apiSendInvitation(onboardingId)
      showToast(
        result?.status === 'sent'
          ? 'Invitation sent successfully.'
          : `Invitation ${result?.status || 'not sent'} — check email configuration.`
      )
      return result
    },
    [showToast]
  )

  // "Send reminder now" (US08 manual trigger). The prototype's sendReminder
  // was per-candidate; the real flow is per-onboarding.
  const sendReminder = useCallback(
    async (onboardingId) => {
      const result = await apiFetch(`/onboarding/${onboardingId}/send-reminder-now`, {
        method: 'POST',
      })
      showToast(
        result?.status === 'sent'
          ? 'Reminder sent successfully.'
          : `Reminder ${result?.status || 'skipped'}${result?.reason ? ` — ${result.reason}` : ''}`
      )
      return result
    },
    [showToast]
  )

  const getCandidate = useCallback((id) => candidates.find((c) => c.id === id), [candidates])

  const refresh = useCallback(() => load(), [load])

  const value = useMemo(
    () => ({
      candidates,
      loading,
      error,
      meta,
      filters,
      setFilters,
      load,
      refresh,
      getCandidate,
      createOnboarding,
      sendInvitation,
      sendReminder,
    }),
    [
      candidates,
      loading,
      error,
      meta,
      filters,
      load,
      refresh,
      getCandidate,
      createOnboarding,
      sendInvitation,
      sendReminder,
    ]
  )
  return <OnboardingContext.Provider value={value}>{children}</OnboardingContext.Provider>
}

export function useOnboarding() {
  const ctx = useContext(OnboardingContext)
  if (!ctx) throw new Error('useOnboarding must be used within OnboardingProvider')
  return ctx
}
