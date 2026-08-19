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
  Upload,
  X,
} from 'lucide-react'

const API_BASE = '/api/v1'

const STATUS_CONFIG = {
  completed: { icon: CheckCircle, color: 'text-green-500', bg: 'bg-green-100', text: 'text-green-700', label: 'Completed', border: 'border-l-green-500' },
  uploaded: { icon: CheckCircle, color: 'text-emerald-500', bg: 'bg-emerald-100', text: 'text-emerald-700', label: 'Uploaded', border: 'border-l-emerald-500' },
  pending: { icon: Clock, color: 'text-amber-500', bg: 'bg-amber-100', text: 'text-amber-700', label: 'Pending', border: 'border-l-amber-400' },
  missing: { icon: AlertCircle, color: 'text-red-500', bg: 'bg-red-100', text: 'text-red-700', label: 'Missing', border: 'border-l-red-500' },
}

const ALLOWED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.gif']

function DocumentCard({ doc, index, onUploadSuccess }) {
  const [expanded, setExpanded] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState(null) // null | 'success' | 'error'
  const [uploadError, setUploadError] = useState('')
  const status = STATUS_CONFIG[doc.status] || STATUS_CONFIG.pending
  const StatusIcon = status.icon

  const formatAccepted = doc.accepted_formats?.split(',').map(f => f.trim()) || ['PDF', 'JPG', 'PNG']

  async function handleUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return

    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setUploadStatus('error')
      setUploadError(`Invalid file type. Allowed: ${formatAccepted.join(', ')}`)
      return
    }

    setUploading(true)
    setUploadStatus(null)
    setUploadError('')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(`${API_BASE}/onboarding/document/${doc.id}/upload`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const err = await response.json()
        setUploadStatus('error')
        setUploadError(err.detail || 'Upload failed')
      } else {
        const result = await response.json()
        setUploadStatus('success')
        setUploadError('')
        onUploadSuccess(doc.id, result)
      }
    } catch (err) {
      setUploadStatus('error')
      setUploadError(err.message || 'Network error')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className={`bg-white rounded-xl border border-slate-200 overflow-hidden transition-all duration-200 hover:border-primary-300 hover:shadow-md ${status.border}`}>
      {/* Main row */}
      <div className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-4 flex-1 min-w-0">
            {/* Step number / status icon */}
            <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-all ${
              doc.status === 'completed' || doc.status === 'uploaded'
                ? 'bg-green-100 text-green-700'
                : 'bg-slate-100 text-slate-600'
            }`}>
              {doc.status === 'completed' || doc.status === 'uploaded' ? (
                <StatusIcon className="w-5 h-5" />
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

              {/* Upload result message */}
              {uploadStatus === 'success' && (
                <div className="mt-2 flex items-center gap-2 text-sm text-green-600">
                  <CheckCircle className="w-4 h-4" />
                  <span>File uploaded successfully!</span>
                </div>
              )}
              {uploadStatus === 'error' && (
                <div className="mt-2 flex items-center gap-2 text-sm text-red-600">
                  <AlertCircle className="w-4 h-4" />
                  <span>{uploadError}</span>
                </div>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 flex-shrink-0">
            {(doc.status === 'pending' || doc.status === 'missing') && (
              <label className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                uploading
                  ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                  : 'bg-primary-600 text-white hover:bg-primary-700 shadow-sm cursor-pointer'
              }`}>
                {uploading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    Upload
                  </>
                )}
                <input
                  type="file"
                  accept={formatAccepted.map(f => {
                    const maps = { PDF: '.pdf', JPG: '.jpg,.jpeg', PNG: '.png', GIF: '.gif' }
                    return maps[f] || ''
                  }).join(',')}
                  onChange={handleUpload}
                  disabled={uploading}
                  className="hidden"
                />
              </label>
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
                  {formatAccepted.map((fmt) => (
                    <span key={fmt} className="inline-flex items-center gap-1 text-xs bg-white border border-slate-200 text-slate-600 px-2 py-0.5 rounded-md">
                      <FileText className="w-3 h-3" />
                      {fmt}
                    </span>
                  ))}
                </div>
              )}
              {doc.status === 'pending' || doc.status === 'missing' ? (
                <p className="mt-2 text-xs text-slate-400 flex items-center gap-1">
                  <HelpCircle className="w-3 h-3" />
                  Click the Upload button to submit this document
                </p>
              ) : null}
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

  function handleUploadSuccess(docId, result) {
    setPortalData((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        documents: prev.documents.map((d) =>
          d.id === docId
            ? { ...d, status: 'uploaded', file_name: result.file_name }
            : d
        ),
      }
    })
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

  const completedCount = (portalData?.completed_documents ??
    portalData?.documents?.filter(
      (d) => d.status === 'completed' || d.status === 'uploaded'
    ).length) || 0
  const totalCount = (portalData?.total_documents ??
    portalData?.documents?.length) || 0
  const progressPercent = portalData?.completion_percentage ??
    (totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0)
  const missingCount = portalData?.documents?.filter((d) => d.status === 'missing').length || 0

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
            Complete your onboarding by uploading the required documents below.
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
                {missingCount > 0 ? ` \u00b7 ${missingCount} missing` : ''}
              </p>
            </div>
            <span className="text-2xl font-bold text-primary-600">{progressPercent}%</span>
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
              All documents have been submitted successfully!
            </div>
          )}
        </div>
      </div>

      {/* Document Checklist */}
      <div className="max-w-3xl mx-auto px-6 py-8">
        <h2 className="text-xl font-bold text-slate-900 mb-1">Required Documents</h2>
        <p className="text-sm text-slate-500 mb-5">
          Click the expand (chevron) icon on each document to view detailed upload
          instructions, accepted file formats, and then upload your file.
        </p>
        <div className="space-y-3">
          {portalData?.documents?.map((doc, index) => (
            <DocumentCard
              key={doc.id}
              doc={doc}
              index={index}
              onUploadSuccess={handleUploadSuccess}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

export default OnboardingPortal
