import { useCallback, useState } from 'react'
import { UploadCloud, CheckCircle2, FileText, Loader2, AlertCircle } from 'lucide-react'
import { uploadDocument } from '../../api/client'

// US12-frontend: real multipart upload — POST /onboarding/document/{id}/upload
// (US03). Keeps the prototype's drag-drop UX and carries over the old
// OnboardingPortal.jsx validation UX (10 MB limit, extension check, backend
// error surfaced inline). The simulated progress bar became an indeterminate
// busy state; the backend call is the source of truth.

const ACCEPTED_EXT = ['.pdf', '.jpg', '.jpeg', '.png', '.gif']
const MAX_SIZE_MB = 10

export default function FileUpload({
  documentId,
  onUploadComplete,
  accept = '.pdf,.jpg,.jpeg,.png,.gif',
}) {
  const [state, setState] = useState('idle') // idle | uploading | success
  const [fileName, setFileName] = useState('')
  const [isDragOver, setIsDragOver] = useState(false)
  const [error, setError] = useState('')

  const runUpload = useCallback(
    async (file) => {
      if (!file) return
      // Client-side validation carried over from the old portal page —
      // matches the backend rules in document_service.validate_file.
      const ext = file.name.includes('.')
        ? '.' + file.name.split('.').pop().toLowerCase()
        : ''
      if (!ACCEPTED_EXT.includes(ext)) {
        setError('Unsupported file type. Allowed: PDF, JPG, PNG, GIF')
        return
      }
      if (file.size > MAX_SIZE_MB * 1024 * 1024) {
        setError(`File size exceeds ${MAX_SIZE_MB}MB limit`)
        return
      }
      if (file.size === 0) {
        setError('Uploaded file is empty')
        return
      }

      setError('')
      setFileName(file.name)
      setState('uploading')
      try {
        await uploadDocument(documentId, file)
        setState('success')
        // Let HR/candidate see the success state, then hand the (real)
        // server response to the parent for refresh.
        window.setTimeout(() => onUploadComplete?.(file), 700)
      } catch (err) {
        setState('idle')
        setError(err.message || 'Upload failed')
      }
    },
    [documentId, onUploadComplete]
  )

  function handleInputChange(e) {
    const file = e.target.files?.[0]
    runUpload(file)
    e.target.value = ''
  }

  function handleDrop(e) {
    e.preventDefault()
    setIsDragOver(false)
    if (state === 'uploading') return
    const file = e.dataTransfer.files?.[0]
    runUpload(file)
  }

  if (state === 'uploading') {
    return (
      <div className="rounded-xl border border-border-soft bg-surface-sunken/60 px-4 py-3.5">
        <div className="flex items-center gap-2.5 text-[13px] font-medium text-ink">
          <Loader2 className="h-4 w-4 animate-spin text-brand" />
          <span className="flex-1 truncate">{fileName}</span>
          <span className="text-xs text-ink-faint">Uploading…</span>
        </div>
      </div>
    )
  }

  if (state === 'success') {
    return (
      <div className="flex items-center gap-2.5 rounded-xl border border-success/25 bg-success-soft px-4 py-3.5">
        <CheckCircle2 className="h-5 w-5 shrink-0 text-success" />
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium text-success">Upload complete</p>
          <p className="truncate text-xs text-success/80">{fileName}</p>
        </div>
      </div>
    )
  }

  return (
    <div>
      <label
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragOver(true)
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-6 text-center transition-colors ${
          isDragOver ? 'border-brand bg-brand-soft' : 'border-border hover:border-ink-faint hover:bg-surface-sunken/60'
        }`}
      >
        <UploadCloud className={`h-5 w-5 ${isDragOver ? 'text-brand' : 'text-ink-faint'}`} />
        <span className="text-[13px] font-medium text-ink">
          <span className="text-brand">Upload a document</span> or drag and drop
        </span>
        <span className="text-xs text-ink-faint">PDF, JPG, PNG or GIF · Maximum 10 MB</span>
        <input type="file" accept={accept} className="hidden" onChange={handleInputChange} />
      </label>
      {error ? (
        <p className="mt-1.5 flex items-start gap-1.5 text-xs text-danger">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {error}
        </p>
      ) : null}
    </div>
  )
}
