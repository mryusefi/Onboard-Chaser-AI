import { Navigate, Outlet, Link } from 'react-router-dom'
import { CheckCircle2, ArrowLeft } from 'lucide-react'

// CandidateLayout — no sidebar. The "HR view" link from the prototype was a
// demo shortcut; the real candidate session is token-scoped and must not
// link into the HR area (which requires login anyway). The link is removed.

export default function CandidateLayout() {
  return (
    <div className="min-h-screen bg-paper">
      <header className="border-b border-border-soft bg-surface">
        <div className="mx-auto flex h-14 max-w-2xl items-center gap-2 px-5">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-brand text-white">
            <CheckCircle2 className="h-4 w-4" />
          </span>
          <span className="font-display text-[14px] font-semibold tracking-tight text-ink">Onboard Chaser</span>
        </div>
      </header>
      <div className="mx-auto max-w-2xl px-5 py-8 sm:py-12">
        <Outlet />
      </div>
    </div>
  )
}
