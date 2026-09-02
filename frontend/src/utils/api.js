// Shared fetch helper for HR-authenticated API calls (US09).
//
// The MVP has no login UI yet (see PROJECT_STATE.md gaps); until it exists,
// an HR JWT can be stored manually after calling POST /api/v1/auth/login:
//   localStorage.setItem('hr_token', '<access_token>')
// authFetch attaches it as a Bearer header when present and falls back to a
// plain fetch otherwise (matching the existing unauthenticated fetch style).
export async function authFetch(url, options = {}) {
  const token = localStorage.getItem('hr_token')
  const headers = {
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
  return fetch(url, { ...options, headers })
}

// Keep in sync with backend MAGIC_TOKEN_EXPIRE_HOURS (app/core/config.py).
// Used for client-side validation of final_reminder_before_expiry_hours.
export const MAGIC_TOKEN_EXPIRE_HOURS = 72
