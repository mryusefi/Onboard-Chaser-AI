import { Routes, Route } from 'react-router-dom'
import HomePage from './pages/HomePage'
import OnboardingPortal from './pages/OnboardingPortal'
import CreateOnboardingPage from './pages/CreateOnboardingPage'
import ReminderSettingsPage from './pages/ReminderSettingsPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/onboard/:token" element={<OnboardingPortal />} />
      <Route path="/admin/onboarding/new" element={<CreateOnboardingPage />} />
      <Route path="/admin/settings/reminders" element={<ReminderSettingsPage />} />
    </Routes>
  )
}

export default App
