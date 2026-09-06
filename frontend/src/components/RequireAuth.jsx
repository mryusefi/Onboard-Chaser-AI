import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

// US12-frontend — route guard for the HR area. Unauthenticated visitors are
// redirected to /login (preserving the intended destination for post-login
// bounce-back). The candidate portal /onboard/:token is NOT guarded — its
// authorization is the magic-link token itself.

export default function RequireAuth() {
  const { isAuthenticated } = useAuth()
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }
  return <Outlet />
}
