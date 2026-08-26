import { Routes, Route } from 'react-router-dom'
import HomePage from './pages/HomePage'
import OnboardingPortal from './pages/OnboardingPortal'
import CreateOnboardingPage from './pages/CreateOnboardingPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/onboard/:token" element={<OnboardingPortal />} />
      <Route path="/admin/onboarding/new" element={<CreateOnboardingPage />} />
    </Routes>
  )
}

export default App
