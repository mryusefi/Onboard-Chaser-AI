import { Outlet } from 'react-router-dom'
import Sidebar from '../components/Sidebar'

// US12-frontend — HR shell: fixed sidebar + content outlet. Route-guarded by
// RequireAuth (redirects to /login when no HR session).

export default function HRLayout() {
  return (
    <div className="flex min-h-screen bg-paper">
      <Sidebar />
      <main className="min-w-0 flex-1">
        <Outlet />
      </main>
    </div>
  )
}
