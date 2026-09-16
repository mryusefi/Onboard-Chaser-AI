import { Outlet } from 'react-router-dom'
import { CheckCircle2 } from 'lucide-react'
import ThemeToggle from '../components/ThemeToggle'

// CandidateLayout — no sidebar. The "HR view" link from the prototype was a
// demo shortcut; the real candidate session is token-scoped and must not
// link into the HR area (which requires login anyway). The link is removed.
// Part D: the theme toggle IS offered here — dark mode is a candidate-facing
// preference too (they spend the most time on this page).

export default function CandidateLayout() {
  return (
    <div className="min-h-screen bg-paper dark:bg-night">
      <header className="border-b border-border-soft dark:border-night-line-soft bg-surface dark:bg-night-surface">
        <div className="mx-auto flex h-14 max-w-2xl items-center gap-2 px-5">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-brand text-white dark:bg-brand-night dark:text-night">
            <CheckCircle2 className="h-4 w-4" />
          </span>
          <span className="font-display text-[14px] font-semibold tracking-tight text-ink dark:text-night-ink">Onboard Chaser</span>
          <span className="ml-auto">
            <ThemeToggle />
          </span>
        </div>
      </header>
      <div className="mx-auto max-w-2xl px-5 py-8 sm:py-12">
        <Outlet />
      </div>
    </div>
  )
}
