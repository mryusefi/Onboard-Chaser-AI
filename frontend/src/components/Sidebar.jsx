import { NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, ListChecks, BellRing, CheckCircle2, LogOut } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { logout } from '../api/client'
import { initials } from '../utils/format'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/onboardings', label: 'Onboardings', icon: ListChecks },
  { to: '/reminders', label: 'Reminders', icon: BellRing },
]

export default function Sidebar() {
  const { user, logout: logoutSession } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout() // clears the API token
    logoutSession() // clears the auth context
    navigate('/login')
  }

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-border bg-surface">
      <div className="flex h-16 items-center gap-2.5 border-b border-border-soft px-5">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand text-white">
          <CheckCircle2 className="h-4 w-4" />
        </span>
        <span className="font-display text-[15px] font-semibold tracking-tight text-ink">Onboard Chaser</span>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13.5px] font-medium transition-colors ${
                isActive
                  ? 'bg-brand-soft text-brand-dark'
                  : 'text-ink-soft hover:bg-surface-sunken hover:text-ink'
              }`
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border-soft p-3">
        <div className="flex items-center gap-2.5 rounded-lg px-2 py-2">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-navy text-[11px] font-semibold text-white">
            {initials(user?.email?.split('@')[0] || 'HR')}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-medium text-ink">{user?.email || 'HR user'}</p>
            <p className="truncate text-xs text-ink-faint">{user?.role || 'HR Coordinator'}</p>
          </div>
          <button
            onClick={handleLogout}
            title="Sign out"
            className="shrink-0 rounded-md p-1.5 text-ink-faint hover:bg-surface-sunken hover:text-ink"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  )
}
