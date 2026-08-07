import { Routes, Route } from 'react-router-dom'
import HomePage from './pages/HomePage'
import OnboardingPortal from './pages/OnboardingPortal'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/onboard/:token" element={<OnboardingPortal />} />
    </Routes>
  )
}

export default App
