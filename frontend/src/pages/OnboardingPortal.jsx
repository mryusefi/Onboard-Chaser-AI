import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import {
  Shield,
  CheckCircle,
  Clock,
  AlertCircle,
  FileUp,
  ChevronDown,
  ChevronUp,
  Info,
  FileText,
  HelpCircle,
} from 'lucide-react'

const API_BASE = '/api/v1'

const STATUS_CONFIG = {
  completed: {
    icon: CheckCircle,
    color: 'text-green-500',
    bg: 'bg-green-100',
    text: 'text-green-700',
    label: 'Completed',
    ring: 'ring-green-200',
  },
  uploaded: {
    icon: CheckCircle,
    color: 'text-emerald-500',
    bg: 'bg-emerald-100',
    text: 'text-emerald-700',
    label: 'Uploaded',
    ring: 'ring-emerald-200',
  },
  pending: {
    icon: Clock,
    color: 'text-amber-500',
    bg: 'bg-amber-100',
    text: 'text-amber-700',
    label: 'Pending',
    ring: 'ring-amber-200',
  },
  missing: {
    icon: AlertCircle,
    color: 'text-red-500',
    bg: 'bg-red-100',
    text: 'text-red-700',
    label: 'Missing',
    ring: 'ring-red-200',
  },
}

function DocumentCard({ doc, index }) {
  const [expanded, setExpanded] = useState(false)
  const status = STATUS_CONFIG[doc.status] || STATUS_CONFIG.pending
  const StatusIcon = status.icon

  return (
    <div className={`bg-white rounded-xl border border-slate-200 overflow-hidden transition-all duration-200 hover:border-primary-300 hover:shadow-md ${doc.status === 'completed' || doc.status === 'uploaded' ? 'border-l-4 border-l-green-500' : doc.status === 'missing' ? 'border-l-4 border-l-red-500' : 'border-l-4 border-l-amber-400'}`}>
      {/* Main row */}
      <div className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-4 flex-1 min-w-0">
            {/* Step number */}
            <div className={`flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold ${doc.status === 'completed' || doc.status === 'uploaded' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'}`}>
              {doc.status === 'completed' || doc.status === 'uploaded' ? (
                <CheckCircle className="w-5 h-5" />
              ) : (
                index + 1
              )}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-semibold text-slate-900">{doc.name}</h3>
                {doc.required && (
                  <span className="text-[10px] font-bold uppercase tracking-wider bg-red-50 text-red-600 px-1.5 py-0.5 rounded">
                    Required
                  </span>
                )}
              </div>

              {/* Status badge */}
              <div className="mt-1.5">
                <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${status.bg} ${status.text}`}>
                  <StatusIcon className="w-3 h-3" />
                  {status.label}
                </span>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 flex-shrink-0">
            {(doc.status === 'pending' || doc.status === 'missing') && (
              <button className="flex items-center gap-1.5 bg-primary-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary-700 transition-colors shadow-sm">
                <FileUp className="w-4 h-4" />
                Upload
              </button>
            )}
            {doc.instructions && (
              <button
                onClick={() => setExpanded(!expanded)}
                className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                title="View instructions"
              >
                {expanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Expandable instructions panel */}
      {expanded && doc.instructions && (
        <div className="border-t border-slate-100 bg-slate-50 px-5 py-4">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center mt-0.5">
              <Info className="w-4 h-4 text-blue-600" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-slate-700 mb-1">Upload Instructions</p>
              <p className="text-sm text-slate-600 leading-relaxed">{doc.instructions}</p>
              {doc.accepted_formats && (
                <div className="mt-3 flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-slate-500 font-medium">Accepted formats:</span>
                  {doc.accepted_formats.split(',').map((fmt) => (
                    <span key={fmt.trim()} className="inline-flex items-center gap-1 text-xs bg-white border border-slate-200 text-slate-600 px-2 py-0.5 rounded-md">
                      <FileText className="w-3 h-3" />
                      {fmt.trim()}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

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

  const completedCount = portalData?.documents?.filter(
    (d) => d.status === 'completed' || d.status === 'uploaded'
  ).length || 0
  const totalCount = portalData?.documents?.length || 0
  const requiredCount = portalData?.documents?.filter((d) => d.required).length || 0
  const progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <div className="gradient-bg py-10 pb-16">
        <div className="max-w-3xl mx-auto px-6">
          <div className="flex items-center gap-3 mb-6">
            <Shield className="w-8 h-8 text-blue-200" />
            <span className="text-white font-semibold text-lg">Onboard Chaser AI</span>
          </div>
          <h1 className="text-3xl font-bold text-white">
            Welcome, {portalData.candidate_name}
          </h1>
          <p className="text-blue-100 mt-2">
            Please upload the required documents to complete your onboarding process.
          </p>
        </div>
      </div>

      {/* Progress Card */}
      <div className="max-w-3xl mx-auto px-6 -mt-8">
        <div className="bg-white rounded-2xl shadow-lg p-6 border border-slate-100">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-base font-semibold text-slate-900">Onboarding Progress</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                {completedCount} of {totalCount} documents submitted
                {requiredCount > 0 && ` \u00b7 ${requiredCount} required`}
              </p>
            </div>
            <div className="text-right">
              <span className="text-2xl font-bold text-primary-600">{progressPercent}%</span>
            </div>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-3">
            <div
              className={`h-3 rounded-full transition-all duration-700 ease-out ${
                progressPercent === 100
                  ? 'bg-green-500'
                  : progressPercent >= 50
                  ? 'bg-primary-500'
                  : 'bg-amber-500'
              }`}
              style={{ width: `${progressPercent}%` }}
            ></div>
          </div>
          {progressPercent === 100 && (
            <div className="mt-3 flex items-center gap-2 text-green-600 text-sm font-medium">
              <CheckCircle className="w-4 h-4" />
              All documents have been submitted!
            </div>
          )}
        </div>
      </div>

      {/* Document Checklist */}
      <div className="max-w-3xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Required Documents</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              Click the arrow on each item to view detailed upload instructions.
            </p>
          </div>
          <button className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-primary-600 transition-colors">
            <HelpCircle className="w-4 h-4" />
            Need help?
          </button>
        </div>

        <div className="space-y-3">
          {portalData?.documents?.map((doc, index) => (
            <DocumentCard key={doc.id} doc={doc} index={index} />
          ))}
        </div>
      </div>
    </div>
  )
}

export default OnboardingPortal
