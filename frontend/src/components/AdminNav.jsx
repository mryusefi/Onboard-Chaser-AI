import { NavLink } from 'react-router-dom'
import { LayoutDashboard, UserPlus, Bell } from 'lucide-react'

// US10 — minimal nav bar shared by the /admin/* pages (no admin shell existed
// before; this gives HR one-click navigation between the admin pages).
const LINKS = [
  { to: '/admin/onboarding', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/admin/onboarding/new', label: 'New Onboarding', icon: UserPlus },
  { to: '/admin/settings/reminders', label: 'Reminder Settings', icon: Bell },
]

export default function AdminNav() {
  return (
    <nav className="flex flex-wrap items-center gap-1 mb-6 bg-white rounded-xl border border-slate-200 p-1.5 shadow-sm">
      {LINKS.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            `flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
              isActive
                ? 'bg-primary-600 text-white'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`
          }
        >
          <Icon className="w-4 h-4" /> {label}
        </NavLink>
      ))}
    </nav>
  )
}
