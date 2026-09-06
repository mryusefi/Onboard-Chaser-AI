import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

export default function Modal({ open, onClose, title, children, footer, size = 'md' }) {
  const dialogRef = useRef(null)

  useEffect(() => {
    if (!open) return
    function handleKey(e) {
      if (e.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', handleKey)
    dialogRef.current?.focus()
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handleKey)
      document.body.style.overflow = prevOverflow
    }
  }, [open, onClose])

  if (!open) return null

  const widthClass = size === 'lg' ? 'max-w-lg' : size === 'sm' ? 'max-w-sm' : 'max-w-md'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 animate-fade-in"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose?.()
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={`animate-modal-in w-full ${widthClass} rounded-2xl border border-border bg-surface shadow-pop outline-none`}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border-soft px-6 py-5">
          <h2 className="font-display text-lg font-semibold text-ink">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="-m-1 shrink-0 rounded-lg p-1.5 text-ink-faint hover:bg-surface-sunken hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="px-6 py-5">{children}</div>
        {footer ? (
          <div className="flex items-center justify-end gap-2.5 border-t border-border-soft px-6 py-4">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  )
}
