import { Shield, FileCheck, Clock } from 'lucide-react'

function HomePage() {
  return (
    <div className="min-h-screen gradient-bg">
      <div className="max-w-4xl mx-auto px-6 py-20 text-center">
        <h1 className="text-5xl font-bold text-white mb-4">
          Onboard Chaser AI
        </h1>
        <p className="text-xl text-blue-100 mb-12">
          Streamline your employee onboarding. Secure. Automated. Effortless.
        </p>

        <div className="grid md:grid-cols-3 gap-8 mt-16">
          <div className="bg-white/10 backdrop-blur rounded-xl p-8">
            <Shield className="w-12 h-12 text-blue-200 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-white mb-2">Secure Access</h3>
            <p className="text-blue-100 text-sm">
              Magic-link authentication ensures only verified candidates access their portal.
            </p>
          </div>

          <div className="bg-white/10 backdrop-blur rounded-xl p-8">
            <FileCheck className="w-12 h-12 text-blue-200 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-white mb-2">Document Collection</h3>
            <p className="text-blue-100 text-sm">
              Candidates upload required documents directly through a secure portal.
            </p>
          </div>

          <div className="bg-white/10 backdrop-blur rounded-xl p-8">
            <Clock className="w-12 h-12 text-blue-200 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-white mb-2">Auto Reminders</h3>
            <p className="text-blue-100 text-sm">
              Automated follow-ups keep your onboarding on track without manual effort.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default HomePage
