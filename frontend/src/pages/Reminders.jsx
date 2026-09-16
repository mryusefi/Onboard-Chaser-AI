import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import Topbar from '../components/Topbar'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import {
  fetchReminderConfig,
  updateReminderConfig,
} from '../api/client'
import { useToast } from '../context/ToastContext'

// US12-frontend: backed by the real GET/PUT /api/v1/settings/reminders
// (US09 singleton ReminderConfig). The prototype's fake rule toggles are
// replaced by the five real fields; inline validation mirrors the backend.

const MAGIC_TOKEN_EXPIRE_HOURS = 72

const FIELDS = [
  {
    key: 'reminder_frequency_hours',
    label: 'Reminder frequency (hours)',
    help: 'Minimum time between two reminder emails for the same candidate.',
    min: 1,
  },
  {
    key: 'first_reminder_after_hours',
    label: 'First reminder after (hours)',
    help: 'Quiet period after the invitation before the first reminder may be sent.',
    min: 0,
  },
  {
    key: 'final_reminder_before_expiry_hours',
    label: 'Final warning before expiry (hours)',
    help: `Send a last warning this many hours before the portal link expires (below the ${MAGIC_TOKEN_EXPIRE_HOURS}h lifetime).`,
    min: 1,
  },
  {
    key: 'max_reminders_per_onboarding',
    label: 'Max reminders per candidate',
    help: 'Hard cap of reminder emails per onboarding.',
    min: 1,
  },
]

function Toggle({ checked, onChange, disabled }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={onChange}
      className={`relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50 ${
        checked ? 'bg-brand' : 'bg-border'
      }`}
    >
      <span
        className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
          checked ? 'translate-x-[22px]' : 'translate-x-0.5'
        }`}
      />
    </button>
  )
}

function validate(form) {
  const errors = {}
  for (const f of FIELDS) {
    const v = Number(form[f.key])
    if (!Number.isInteger(v)) errors[f.key] = 'Must be a whole number'
    else if (v < f.min) errors[f.key] = `Must be at least ${f.min}`
    else if (f.key === 'final_reminder_before_expiry_hours' && v >= MAGIC_TOKEN_EXPIRE_HOURS)
      errors[f.key] = `Must be below the ${MAGIC_TOKEN_EXPIRE_HOURS}h link lifetime`
  }
  return errors
}

export default function Reminders() {
  const { showToast } = useToast()
  const [form, setForm] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [fieldErrors, setFieldErrors] = useState({})

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        // GET /settings/reminders auto-creates the config row on first read.
        const data = await fetchReminderConfig()
        if (!cancelled) setForm(data)
      } catch (err) {
        if (!cancelled) setLoadError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  function setField(key, value) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSave(e) {
    e.preventDefault()
    const errors = validate(form)
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) return
    setSaving(true)
    try {
      const saved = await updateReminderConfig({
        reminder_frequency_hours: Number(form.reminder_frequency_hours),
        first_reminder_after_hours: Number(form.first_reminder_after_hours),
        final_reminder_before_expiry_hours: Number(form.final_reminder_before_expiry_hours),
        max_reminders_per_onboarding: Number(form.max_reminders_per_onboarding),
        is_enabled: form.is_enabled,
      })
      setForm(saved)
      showToast('Reminder settings saved.')
    } catch (err) {
      showToast(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div>
        <Topbar eyebrow="Reminders" title="Automated reminders" />
        <div className="flex items-center justify-center gap-2 py-20 text-sm text-ink-faint">
          <Loader2 className="h-5 w-5 animate-spin" /> Loading settings…
        </div>
      </div>
    )
  }

  if (loadError) {
    return (
      <div>
        <Topbar eyebrow="Reminders" title="Automated reminders" />
        <div className="px-8 py-10">
          <div className="rounded-xl border border-danger/25 bg-danger-soft px-4 py-3 text-sm text-danger">
            {loadError}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="pb-16">
      <Topbar
        eyebrow="Reminders"
        title="Automated reminders"
        subtitle="Automatically follow up when onboarding documents are incomplete."
      />

      <div className="px-8 py-7">
        <form onSubmit={handleSave} className="max-w-3xl">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {FIELDS.map((f) => (
              <Card key={f.key} className="p-5">
                <p className="text-[13.5px] font-semibold text-ink">{f.label}</p>
                <p className="mt-1 text-xs text-ink-faint">{f.help}</p>
                <input
                  type="number"
                  value={form[f.key]}
                  onChange={(e) => setField(f.key, e.target.value)}
                  className={`mt-3 h-10 w-full rounded-lg border bg-surface px-3 text-[13.5px] text-ink focus:outline-none ${
                    fieldErrors[f.key] ? 'border-danger' : 'border-border focus:border-brand'
                  }`}
                />
                {fieldErrors[f.key] && (
                  <p className="mt-1.5 text-xs font-medium text-danger">{fieldErrors[f.key]}</p>
                )}
              </Card>
            ))}

            {/* Master kill switch */}
            <Card className="p-5 sm:col-span-2">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[13.5px] font-semibold text-ink">Reminders enabled</p>
                  <p className="mt-1 text-xs text-ink-faint">
                    Turn off to pause all automated reminders (the hourly scan skips every
                    onboarding while disabled).
                  </p>
                </div>
                <Toggle
                  checked={form.is_enabled}
                  disabled={saving}
                  onChange={() => setField('is_enabled', !form.is_enabled)}
                />
              </div>
            </Card>
          </div>

          <div className="mt-5 flex justify-end">
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving…' : 'Save reminder settings'}
            </Button>
          </div>
        </form>

        <p className="mt-6 max-w-3xl text-xs text-ink-faint">
          The scan runs hourly (REMINDER_SCAN_INTERVAL_MINUTES, deployment setting). Frequency,
          quiet period, expiry warning window, cap and this kill switch are the HR-tunable
          knobs; the beat interval itself changes only with a worker restart.
        </p>
      </div>
    </div>
  )
}
