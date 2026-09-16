// US12-frontend — central API client.
// Uses fetch (consistent with the previous per-story pages, no new deps).
// Auth: HR JWT from localStorage ('hr_token'), attached to every request.
// 401 responses raise ApiError(401) so the route guard can redirect to /login.

export const API_BASE = '/api/v1'

export function getToken() {
  return localStorage.getItem('hr_token') || ''
}

export function setToken(token) {
  if (token) localStorage.setItem('hr_token', token)
  else localStorage.removeItem('hr_token')
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function parseBody(resp) {
  const text = await resp.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export async function apiFetch(path, options = {}) {
  const token = getToken()
  const headers = { ...(options.headers || {}) }
  if (token) headers.Authorization = `Bearer ${token}`
  if (options.body && typeof options.body === 'string') {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json'
  }
  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers })
  let body = null
  if (!options.raw) {
    body = await parseBody(resp)
    if (!resp.ok) {
      const msg =
        (body && (typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail))) ||
        `Request failed (${resp.status})`
      throw new ApiError(msg, resp.status)
    }
  }
  return resp.ok ? body : resp
}

// ── HR auth ─────────────────────────────────────────────────────────────
export async function login(email, password) {
  // POST /api/v1/auth/login takes JSON {email, password} (UserLogin schema)
  const data = await apiFetch('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  setToken(data.access_token)
  return data
}

export function logout() {
  setToken('')
}

// ── Onboardings (US10 list, US11 detail) ────────────────────────────────
export function fetchOnboardings({ status, needsAttention, search, page = 1, pageSize = 20 } = {}) {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (needsAttention !== undefined && needsAttention !== null && needsAttention !== '') {
    params.set('needs_attention', String(needsAttention))
  }
  if (search && search.trim()) params.set('search', search.trim())
  params.set('page', String(page))
  params.set('page_size', String(pageSize))
  return apiFetch(`/onboarding/?${params.toString()}`)
}

export const fetchOnboardingDetail = (id) => apiFetch(`/onboarding/${id}/detail`)

export const fetchReminderHistory = (onboardingId) =>
  apiFetch(`/onboarding/${onboardingId}/reminders`)

// ── Create flow (US06/US07) ─────────────────────────────────────────────
export const createFullOnboarding = (payload) =>
  apiFetch('/onboarding/create-full', { method: 'POST', body: JSON.stringify(payload) })

// US01: fresh magic link for manual copy/share (the create-full response
// does not include the token; this generates one on demand). Returns
// { magic_link, expires_at }.
export const generateMagicLink = (candidateId) =>
  apiFetch('/onboarding/magic-link', {
    method: 'POST',
    body: JSON.stringify({ candidate_id: candidateId }),
  })

export const sendInvitation = (onboardingId) =>
  apiFetch(`/onboarding/${onboardingId}/send-invitation`, { method: 'POST' })

// ── Documents (US11) ────────────────────────────────────────────────────
export const fetchAccessUrl = (documentId) =>
  apiFetch(`/documents/${documentId}/access-url`)

export const updateVerification = (documentId, verification_status, verification_note) =>
  apiFetch(`/documents/${documentId}/verification`, {
    method: 'PATCH',
    body: JSON.stringify({
      verification_status,
      ...(verification_note ? { verification_note } : {}),
    }),
  })

// Multipart upload (US03) — no JSON content-type; browser sets the boundary.
export const uploadDocument = (documentId, file) => {
  const form = new FormData()
  form.append('file', file)
  return apiFetch(`/onboarding/document/${documentId}/upload`, {
    method: 'POST',
    body: form,
  })
}

// ── Reminder settings (US09) ────────────────────────────────────────────
export const fetchReminderConfig = () => apiFetch('/settings/reminders')
export const updateReminderConfig = (payload) =>
  apiFetch('/settings/reminders', { method: 'PUT', body: JSON.stringify(payload) })

// ── Candidate portal (US01–US05, token-based) ───────────────────────────
export const fetchPortal = (token) => apiFetch(`/onboarding/portal/${token}`)
export const updateDocumentStatus = (documentId, status) =>
  apiFetch(`/onboarding/document/${documentId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
