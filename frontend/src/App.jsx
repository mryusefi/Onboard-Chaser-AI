import { Routes, Route } from 'react-router-dom'
import HomePage from './pages/HomePage'
import OnboardingPortal from './pages/OnboardingPortal'
import CreateOnboardingPage from './pages/CreateOnboardingPage'
import ReminderSettingsPage from './pages/ReminderSettingsPage'
import OnboardingDashboardPage from './pages/OnboardingDashboardPage'
import OnboardingDetailPage from './pages/OnboardingDetailPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/onboard/:token" element={<OnboardingPortal />} />
      <Route path="/admin/onboarding" element={<OnboardingDashboardPage />} />
      <Route path="/admin/onboarding/new" element={<CreateOnboardingPage />} />
      {/* US10 placeholder — US11 extends this with document-level detail. */}
      <Route path="/admin/onboarding/:id" element={<OnboardingDetailPage />} />
      <Route path="/admin/settings/reminders" element={<ReminderSettingsPage />} />
    </Routes>
  )
}

export default App
