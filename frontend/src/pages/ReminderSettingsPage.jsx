import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Bell, Loader2, AlertCircle, CheckCircle2, Clock, Repeat, Ban, Timer,
} from 'lucide-react'
import { authFetch, MAGIC_TOKEN_EXPIRE_HOURS } from '../utils/api'

// US09 — HR settings for the global reminder configuration.
// Inline validation mirrors the backend rules exactly:
//   reminder_frequency_hours          >= 1
//   first_reminder_after_hours        >= 0
//   final_reminder_before_expiry_hours >= 1 and < MAGIC_TOKEN_EXPIRE_HOURS
//   max_reminders_per_onboarding      >= 1

const INITIAL = {
  reminder_frequency_hours: 24,
  first_reminder_after_hours: 24,
  final_reminder_before_expiry_hours: 24,
  max_reminders_per_onboarding: 3,
  is_enabled: true,
}

const FIELDS = [
  {
    key: 'reminder_frequency_hours',
    label: 'Reminder frequency (hours)',
    help: 'Minimum time between two reminder emails for the same candidate.',
    icon: Repeat,
    min: 1,
  },
  {
    key: 'first_reminder_after_hours',
    label: 'First reminder after (hours)',
    help: 'Quiet period after the invitation before the first reminder may be sent.',
    icon: Clock,
    min: 0,
  },
  {
    key: 'final_reminder_before_expiry_hours',
    label: 'Final warning before expiry (hours)',
    help: `Send a last warning this many hours before the portal link expires (must be below the ${MAGIC_TOKEN_EXPIRE_HOURS}h link lifetime).`,
    icon: Timer,
    min: 1,
  },
  {
    key: 'max_reminders_per_onboarding',
    label: 'Max reminders per candidate',
    help: 'Hard cap of reminder emails per onboarding, however late the candidate is.',
    icon: Ban,
    min: 1,
  },
]

function validate(form) {
  const errors = {}
  for (const f of FIELDS) {
    const v = Number(form[f.key])
    if (!Number.isInteger(v)) {
      errors[f.key] = 'Must be a whole number'
    } else if (v < f.min) {
      errors[f.key] = `Must be at least ${f.min}`
    } else if (f.key === 'final_reminder_before_expiry_hours' && v >= MAGIC_TOKEN_EXPIRE_HOURS) {
      errors[f.key] = `Must be below the ${MAGIC_TOKEN_EXPIRE_HOURS}h link lifetime`
    }
  }
  return errors
}

export default function ReminderSettingsPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState(INITIAL)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [saveError, setSaveError] = useState(null)
  const [success, setSuccess] = useState(false)
  const [fieldErrors, setFieldErrors] = useState({})

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const resp = await authFetch('/api/v1/settings/reminders')
        const data = await resp.json()
        if (!resp.ok) throw new Error(data.detail || 'Failed to load reminder settings')
        if (!cancelled) {
          setForm({
            reminder_frequency_hours: data.reminder_frequency_hours,
            first_reminder_after_hours: data.first_reminder_after_hours,
            final_reminder_before_expiry_hours: data.final_reminder_before_expiry_hours,
            max_reminders_per_onboarding: data.max_reminders_per_onboarding,
            is_enabled: data.is_enabled,
          })
        }
      } catch (err) {
        if (!cancelled) setLoadError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  const setField = (key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setForm((prev) => ({ ...prev, [key]: value }))
    setSuccess(false)
  }

  const save = async (e) => {
    e.preventDefault()
    setSaveError(null)
    setSuccess(false)

    const errors = validate(form)
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) return

    setSaving(true)
    try {
      const resp = await authFetch('/api/v1/settings/reminders', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reminder_frequency_hours: Number(form.reminder_frequency_hours),
          first_reminder_after_hours: Number(form.first_reminder_after_hours),
          final_reminder_before_expiry_hours: Number(form.final_reminder_before_expiry_hours),
          max_reminders_per_onboarding: Number(form.max_reminders_per_onboarding),
          is_enabled: form.is_enabled,
        }),
      })
      const data = await resp.json()
      if (!resp.ok) {
        // Surface backend 422 detail inline on the offending form.
        setSaveError(typeof data.detail === 'string' ? data.detail : 'Failed to save settings')
        return
      }
      setForm({
        reminder_frequency_hours: data.reminder_frequency_hours,
        first_reminder_after_hours: data.first_reminder_after_hours,
        final_reminder_before_expiry_hours: data.final_reminder_before_expiry_hours,
        max_reminders_per_onboarding: data.max_reminders_per_onboarding,
        is_enabled: data.is_enabled,
      })
      setSuccess(true)
    } catch (err) {
      setSaveError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 py-10 px-4">
      <div className="max-w-2xl mx-auto">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 mb-4"
        >
          <ArrowLeft className="w-4 h-4" /> Back to home
        </button>

        <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-8">
          <div className="flex items-center gap-3 mb-1">
            <Bell className="w-6 h-6 text-primary-600" />
            <h1 className="text-2xl font-bold text-slate-900">Reminder Settings</h1>
          </div>
          <p className="text-sm text-slate-500 mb-6">
            These rules apply to every onboarding. The automated scan runs hourly and
            emails candidates whose documents are still pending.
          </p>

          {loadError && (
            <div className="mb-5 flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" /> {loadError}
            </div>
          )}

          {loading ? (
            <div className="flex items-center gap-2 text-sm text-slate-500 py-4">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading settings…
            </div>
          ) : (
            <form onSubmit={save} className="space-y-5">
              {success && (
                <div className="flex items-start gap-2 bg-green-50 border border-green-200 rounded-xl p-4 text-sm text-green-700">
                  <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />
                  Settings saved — the next automated scan will use these values.
                </div>
              )}
              {saveError && (
                <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
                  <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" /> {saveError}
                </div>
              )}

              {FIELDS.map(({ key, label, help, icon: Icon }) => (
                <div key={key}>
                  <label htmlFor={key} className="flex items-center gap-2 text-sm font-medium text-slate-800 mb-1.5">
                    <Icon className="w-4 h-4 text-slate-400" /> {label}
                  </label>
                  <input
                    id={key}
                    type="number"
                    value={form[key]}
                    onChange={setField(key)}
                    className={`w-full px-4 py-2.5 rounded-xl border focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                      fieldErrors[key]
                        ? 'border-red-300 bg-red-50'
                        : 'border-slate-200'
                    }`}
                  />
                  <p className="mt-1 text-xs text-slate-500">{help}</p>
                  {fieldErrors[key] && (
                    <p className="mt-1 text-xs font-medium text-red-600">{fieldErrors[key]}</p>
                  )}
                </div>
              ))}

              {/* Kill switch */}
              <label className="flex items-center gap-3 px-4 py-3 rounded-xl border border-slate-200 cursor-pointer hover:bg-slate-50">
                <input
                  type="checkbox"
                  checked={form.is_enabled}
                  onChange={setField('is_enabled')}
                  className="w-4 h-4 accent-primary-600"
                />
                <span className="text-sm font-medium text-slate-800">
                  Reminders enabled
                </span>
                <span className="text-xs text-slate-500">
                  (turn off to pause all automated reminders)
                </span>
              </label>

              <button
                type="submit"
                disabled={saving}
                className="w-full py-3 rounded-xl font-semibold text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {saving ? (
                  <><Loader2 className="w-5 h-5 animate-spin" /> Saving…</>
                ) : (
                  'Save Settings'
                )}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
