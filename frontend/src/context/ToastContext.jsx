import { createContext, useCallback, useContext, useRef, useState } from 'react'
import { CheckCircle2, X } from 'lucide-react'

const ToastContext = createContext(null)

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const counter = useRef(0)

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const showToast = useCallback(
    (message) => {
      const id = ++counter.current
      setToasts((prev) => [...prev, { id, message }])
      window.setTimeout(() => dismiss(id), 3200)
    },
    [dismiss]
  )

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div
        className="fixed bottom-5 right-5 z-[100] flex w-[min(360px,calc(100vw-2.5rem))] flex-col gap-2"
        aria-live="polite"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className="animate-toast-in flex items-start gap-2.5 rounded-xl border border-border bg-ink px-4 py-3 shadow-pop"
          >
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" style={{ color: '#5FCFC0' }} />
            <p className="flex-1 text-[13px] leading-snug text-white">{t.message}</p>
            <button
              onClick={() => dismiss(t.id)}
              className="shrink-0 rounded-md p-0.5 text-white/50 hover:text-white/90"
              aria-label="Dismiss notification"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
