import { useState, useEffect, useCallback } from 'react'
import { Bell, Loader2, AlertCircle, RefreshCw, Send, CheckCircle2 } from 'lucide-react'
import { authFetch } from '../utils/api'

// US08/US09 — Reminder history for one onboarding, with a manual
// send-reminder-now trigger. Status chips reuse the US07 invitation
// status-chip styling pattern.
const STATUS_CHIP = {
  sent: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  skipped: 'bg-slate-100 text-slate-600',
}

const TYPE_LABEL = {
  midway: 'Midway',
  expiry_warning: 'Expiry warning',
}

export default function ReminderHistory({ onboardingId }) {
  const [logs, setLogs] = useState(null) // null = loading
  const [error, setError] = useState(null)
  const [sending, setSending] = useState(false)
  const [sendNote, setSendNote] = useState(null) // { kind: 'success'|'error', text }

  const load = useCallback(async () => {
    setError(null)
    try {
      const resp = await authFetch(`/api/v1/onboarding/${onboardingId}/reminders`)
      if (resp.status === 401) {
        throw new Error('Not authorized — sign in as HR (no valid token found).')
      }
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.detail || 'Failed to load reminder history')
      setLogs(data)
    } catch (err) {
      setError(err.message)
    }
  }, [onboardingId])

  useEffect(() => {
    load()
  }, [load])

  const sendNow = async () => {
    setSending(true)
    setSendNote(null)
    try {
      const resp = await authFetch(`/api/v1/onboarding/${onboardingId}/send-reminder-now`, {
        method: 'POST',
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.detail || 'Failed to send reminder')
      const kind = data.status === 'sent' ? 'success' : 'error'
      setSendNote({
        kind,
        text:
          data.status === 'sent'
            ? 'Reminder sent to candidate.'
            : `Reminder ${data.status}${data.reason ? ` — ${data.reason}` : ''}`,
      })
      await load()
    } catch (err) {
      setSendNote({ kind: 'error', text: err.message })
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="border-t border-slate-200 pt-6">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
          <Bell className="w-4 h-4 text-primary-600" /> Reminder History
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            title="Reload history"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={sendNow}
            disabled={sending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {sending ? (
              <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Sending…</>
            ) : (
              <><Send className="w-3.5 h-3.5" /> Send reminder now</>
            )}
          </button>
        </div>
      </div>

      {sendNote && (
        <div
          className={`mb-3 flex items-start gap-2 rounded-xl p-3 text-sm ${
            sendNote.kind === 'success'
              ? 'bg-green-50 border border-green-200 text-green-700'
              : 'bg-red-50 border border-red-200 text-red-700'
          }`}
        >
          {sendNote.kind === 'success' ? (
            <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          )}
          {sendNote.text}
        </div>
      )}

      {error && (
        <div className="mb-3 flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" /> {error}
        </div>
      )}

      {logs === null && !error && (
        <div className="flex items-center gap-2 text-sm text-slate-500 py-2">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading…
        </div>
      )}

      {logs !== null && logs.length === 0 && (
        <p className="text-sm text-slate-500 py-2">
          No reminders yet. Automated reminders are sent by the scheduled scan; use
          “Send reminder now” for an immediate one.
        </p>
      )}

      {logs !== null && logs.length > 0 && (
        <ul className="space-y-2">
          {logs.map((log) => (
            <li
              key={log.id}
              className="flex items-center gap-3 px-4 py-2.5 rounded-xl border border-slate-200"
            >
              <span
                className={`text-xs font-semibold px-3 py-1 rounded-full capitalize ${
                  STATUS_CHIP[log.status] || STATUS_CHIP.skipped
                }`}
              >
                {log.status}
              </span>
              <span className="text-sm font-medium text-slate-800">
                {TYPE_LABEL[log.reminder_type] || log.reminder_type}
              </span>
              <span className="ml-auto text-xs text-slate-500">
                {log.sent_at ? new Date(log.sent_at).toLocaleString() : '—'}
              </span>
            </li>
          ))}
          {logs.some((l) => l.reason) && (
            <li className="pt-1">
              <details className="text-xs text-slate-500">
                <summary className="cursor-pointer hover:text-slate-700">
                  Show details / skip reasons
                </summary>
                <ul className="mt-2 space-y-1">
                  {logs
                    .filter((l) => l.reason)
                    .map((l) => (
                      <li key={`reason-${l.id}`}>
                        <span className="font-medium capitalize">{l.status}</span>
                        {l.sent_at && ` · ${new Date(l.sent_at).toLocaleString()}`} — {l.reason}
                      </li>
                    ))}
                </ul>
              </details>
            </li>
          )}
        </ul>
      )}
    </div>
  )
}
