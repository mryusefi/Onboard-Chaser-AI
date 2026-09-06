import { Routes, Route, Navigate, Link } from 'react-router-dom'
import HRLayout from './layouts/HRLayout'
import CandidateLayout from './layouts/CandidateLayout'
import RequireAuth from './components/RequireAuth'
import Dashboard from './pages/Dashboard'
import Onboardings from './pages/Onboardings'
import CandidateDetail from './pages/CandidateDetail'
import CreateOnboarding from './pages/CreateOnboarding'
import Reminders from './pages/Reminders'
import Login from './pages/Login'
import CandidatePortal from './pages/CandidatePortal'

// US12-frontend — final route map.
//
// HR area (RequireAuth → HRLayout with Sidebar):
//   /dashboard            → summary + recent onboardings (US10 list)
//   /onboardings          → full list with server-side filters/pagination
//   /onboardings/:id      → candidate detail (US11: documents, verification,
//                           access-URL preview/download, reminder trail)
//   /create-onboarding    → create flow (US06) + invitation (US07)
//   /reminders            → reminder configuration (US09)
//   /login                → HR sign-in (no guard)
//
// Candidate area (NO guard — magic-link token IS the authorization):
//   /onboard/:token       → candidate portal (US01–US05)
//   SECURITY: the prototype's /candidate/:candidateId route was replaced by
//   the token route. Never "fix" it back to a guessable ID (README section 8).

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route element={<RequireAuth />}>
        <Route element={<HRLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/onboardings" element={<Onboardings />} />
          <Route path="/onboardings/:id" element={<CandidateDetail />} />
          <Route path="/create-onboarding" element={<CreateOnboarding />} />
          <Route path="/reminders" element={<Reminders />} />
        </Route>
      </Route>

      <Route element={<CandidateLayout />}>
        {/* Token-based: signed + expiring magic link, not a guessable ID. */}
        <Route path="/onboard/:token" element={<CandidatePortal />} />
      </Route>

      <Route
        path="*"
        element={
          <div className="flex min-h-screen flex-col items-center justify-center gap-2 bg-paper text-center">
            <p className="font-display text-lg font-semibold text-ink">Page not found</p>
            <Link to="/dashboard" className="text-sm font-medium text-brand-dark hover:underline">
              Back to dashboard
            </Link>
          </div>
        }
      />
    </Routes>
  )
}
