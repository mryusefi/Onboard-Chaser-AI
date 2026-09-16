// US12-frontend — AuthContext: holds the HR session (JWT + user info).
// The JWT lives in localStorage ('hr_token', same key the previous
// per-story pages used) so a page refresh keeps you logged in. The route
// guard redirects /dashboard, /onboardings, etc. to /login when absent.

import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { getToken } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  // `token` is only used as a boolean signal; the actual string lives in
  // localStorage via the api client (single source of truth).
  const [token, setTokenState] = useState(() => !!getToken())
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('hr_user') || 'null')
    } catch {
      return null
    }
  })

  const handleLogin = useCallback((loginResponse) => {
    setTokenState(true)
    try {
      // Decode JWT payload (no verification — UI display only).
      const payload = JSON.parse(atob(loginResponse.access_token.split('.')[1]))
      const info = {
        email: payload.email || '',
        role: 'HR Coordinator',
      }
      localStorage.setItem('hr_user', JSON.stringify(info))
      setUser(info)
    } catch {
      localStorage.removeItem('hr_user')
      setUser(null)
    }
  }, [])

  const handleLogout = useCallback(() => {
    setTokenState(false)
    localStorage.removeItem('hr_user')
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ isAuthenticated: token, user, login: handleLogin, logout: handleLogout }),
    [token, user, handleLogin, handleLogout]
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
