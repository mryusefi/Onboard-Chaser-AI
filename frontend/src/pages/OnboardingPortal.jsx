import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Shield, CheckCircle, Clock, AlertCircle, FileUp } from 'lucide-react'

const API_BASE = '/api/v1'

function OnboardingPortal() {
  const { token } = useParams()
  const [portalData, setPortalData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchPortalData()
  }, [token])

  async function fetchPortalData() {
    try {
      const response = await fetch(`${API_BASE}/onboarding/portal/${token}`)
      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to access portal')
      }
      const data = await response.json()
      setPortalData(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-slate-600">Validating your secure access...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="max-w-md text-center p-8">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-slate-900 mb-2">Access Denied</h2>
          <p className="text-slate-600">{error}</p>
          <p className="text-sm text-slate-400 mt-4">
            Please request a new onboarding link from your HR coordinator.
          </p>
        </div>
      </div>
    )
  }

  const completedCount = portalData?.documents?.filter(d => d.status === 'completed' || d.status === 'uploaded').length || 0
  const totalCount = portalData?.documents?.length || 0
  const progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="gradient-bg py-8">
        <div className="max-w-3xl mx-auto px-6">
          <div className="flex items-center gap-3 mb-4">
            <Shield className="w-8 h-8 text-blue-200" />
            <span className="text-white font-semibold text-lg">Onboard Chaser AI</span>
          </div>
          <h1 className="text-3xl font-bold text-white">Welcome, {portalData.candidate_name}</h1>
          <p className="text-blue-100 mt-1">Complete your onboarding documents below</p>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="max-w-3xl mx-auto px-6 -mt-4">
        <div className="bg-white rounded-xl shadow-lg p-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-slate-700">Onboarding Progress</span>
            <span className="text-sm font-bold text-primary-600">{progressPercent}%</span>
          </div>
          <div className="w-full bg-slate-200 rounded-full h-3">
            <div
              className="bg-primary-600 h-3 rounded-full transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            ></div>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            {completedCount} of {totalCount} documents submitted
          </p>
        </div>
      </div>

      {/* Document List */}
      <div className="max-w-3xl mx-auto px-6 py-8">
        <h2 className="text-xl font-bold text-slate-900 mb-4">Required Documents</h2>
        <div className="space-y-3">
          {portalData?.documents?.map((doc) => (
            <div
              key={doc.id}
              className="bg-white rounded-lg border border-slate-200 p-4 flex items-center justify-between hover:border-primary-300 transition-colors"
            >
              <div className="flex items-center gap-4">
                {doc.status === 'completed' || doc.status === 'uploaded' ? (
                  <CheckCircle className="w-6 h-6 text-green-500 flex-shrink-0" />
                ) : doc.status === 'pending' ? (
                  <Clock className="w-6 h-6 text-amber-500 flex-shrink-0" />
                ) : (
                  <AlertCircle className="w-6 h-6 text-red-500 flex-shrink-0" />
                )}
                <div>
                  <p className="font-medium text-slate-900">{doc.name}</p>
                  {doc.description && (
                    <p className="text-sm text-slate-500">{doc.description}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs font-medium px-2 py-1 rounded-full ${
                  doc.status === 'completed' || doc.status === 'uploaded'
                    ? 'bg-green-100 text-green-700'
                    : doc.status === 'pending'
                    ? 'bg-amber-100 text-amber-700'
                    : 'bg-red-100 text-red-700'
                }`}>
                  {doc.status.charAt(0).toUpperCase() + doc.status.slice(1)}
                </span>
                {(doc.status === 'pending' || doc.status === 'missing') && (
                  <button className="flex items-center gap-1 bg-primary-600 text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-primary-700 transition-colors">
                    <FileUp className="w-4 h-4" />
                    Upload
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default OnboardingPortal
