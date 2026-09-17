// Maintenance pass Item 1/1b — email settings page.
// Shows whether the SERVER has a real Resend key (read-only booleans — the
// API key itself never leaves the backend env), a "Send test email" action
// for the logged-in HR user, and a form for the HR-editable invitation
// email copy (subject/intro/closing/extra instructions). The functional
// parts of the email (portal link, document list, expiry) are not editable.

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Mail, Loader2, AlertCircle, CheckCircle2, Send, ShieldCheck, ShieldAlert,
} from 'lucide-react'
import Topbar from '../components/Topbar'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import { apiFetch } from '../api/client'
import { useToast } from '../context/ToastContext'

const inputCls =
  'h-10 w-full rounded-lg border border-border dark:border-night-line bg-surface dark:bg-night-surface px-3 text-[13.5px] text-ink dark:text-night-ink placeholder:text-ink-faint focus:border-brand dark:focus:border-brand-night focus:outline-none'

export default function EmailSettings() {
  const { showToast } = useToast()
  const [status, setStatus] = useState(null)
  const [tpl, setTpl] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null) // {status,message}
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [s, t] = await Promise.all([
          apiFetch('/settings/email-status'),
          apiFetch('/settings/email-template'),
        ])
        if (!cancelled) { setStatus(s); setTpl(t) }
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  async function sendTest() {
    setTesting(true)
    setTestResult(null)
    try {
      const r = await apiFetch('/settings/email-status/test', { method: 'POST' })
      setTestResult(r)
      showToast(r.message)
    } catch (err) {
      setTestResult({ status: 'error', message: err.message })
    } finally {
      setTesting(false)
    }
  }

  async function saveTemplate(e) {
    e.preventDefault()
    setSaving(true)
    try {
      const saved = await apiFetch('/settings/email-template', {
        method: 'PUT',
        body: JSON.stringify({
          subject_template: tpl.subject_template || null,
          body_intro: tpl.body_intro || null,
          body_closing: tpl.body_closing || null,
          extra_instructions: tpl.extra_instructions || null,
        }),
      })
      setTpl(saved)
      showToast('Invitation email template saved.')
    } catch (err) {
      showToast(err.message)
    } finally {
      setSaving(false)
    }
  }

  function resetTemplate() {
    setTpl({ subject_template: null, body_intro: null, body_closing: null, extra_instructions: null })
  }

  if (loading) {
    return (
      <div>
        <Topbar eyebrow="Settings" title="Email" />
        <div className="flex items-center justify-center gap-2 py-20 text-sm text-ink-faint dark:text-night-ink-faint">
          <Loader2 className="h-5 w-5 animate-spin" /> Loading email settings…
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div>
        <Topbar eyebrow="Settings" title="Email" />
        <div className="px-8 py-10">
          <div className="rounded-xl border border-danger/25 dark:border-danger-night/25 bg-danger-soft dark:bg-danger-night-soft px-4 py-3 text-sm text-danger dark:text-danger-night">{error}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="pb-16">
      <Topbar eyebrow="Settings" title="Email" subtitle="Invitation email delivery for this server." />

      <div className="px-8 py-7 max-w-3xl">
        {/* ── Delivery status (read-only; key stays server-side) ─────── */}
        <Card className="p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="font-display text-base font-semibold text-ink dark:text-night-ink flex items-center gap-2">
                {status.resend_configured
                  ? <ShieldCheck className="h-4 w-4 text-success dark:text-success-night" />
                  : <ShieldAlert className="h-4 w-4 text-warning dark:text-warning-night" />}
                Delivery status
              </h2>
              <p className="mt-1 text-xs text-ink-faint dark:text-night-ink-faint">
                Email sending is a server-level capability (RESEND_API_KEY lives in the
                backend environment — never in the database, like the R2 credentials).
              </p>
            </div>
            <Badge status={status.resend_configured ? 'verified' : 'not_sent'} withIcon={false}>
              {status.resend_configured ? 'Configured' : 'Not configured'}
            </Badge>
          </div>

          {!status.resend_configured && status.setup_hint && (
            <div className="mt-3 flex items-start gap-2 rounded-xl border border-warning/25 dark:border-warning-night/25 bg-warning-soft dark:bg-warning-night-soft px-4 py-3 text-[13px] text-warning dark:text-warning-night">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {status.setup_hint}
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button size="sm" icon={testing ? Loader2 : Send} disabled={testing} onClick={sendTest}>
              {testing ? 'Sending…' : 'Send test email to me'}
            </Button>
            {status.email_from && (
              <span className="text-xs text-ink-faint dark:text-night-ink-faint">
                From: <span className="font-mono">{status.email_from}</span>
              </span>
            )}
          </div>

          {testResult && (
            <div className={`mt-3 flex items-start gap-2 rounded-xl px-4 py-3 text-[13px] ${
              testResult.status === 'sent'
                ? 'bg-success-soft dark:bg-success-night-soft text-success dark:text-success-night'
                : 'bg-danger-soft dark:bg-danger-night-soft text-danger dark:text-danger-night'
            }`}>
              {testResult.status === 'sent'
                ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                : <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />}
              <span className="font-medium">{testResult.status}:</span> {testResult.message}
            </div>
          )}
        </Card>

        {/* ── Invitation template (HR-editable copy) ──────────────────── */}
        <Card className="p-6 mt-6">
          <h2 className="font-display text-base font-semibold text-ink dark:text-night-ink">Invitation email template</h2>
          <p className="mt-1 text-xs text-ink-faint dark:text-night-ink-faint">
            Only the copy is editable. The portal link, the document list and the expiry
            notice are always added automatically and cannot be removed. Leave a field
            empty to use the built-in default. Available placeholders in the subject:
            {' '}<code className="font-mono">{'{candidate_first_name}'}</code>,{' '}
            <code className="font-mono">{'{company_name}'}</code>.
          </p>

          <form onSubmit={saveTemplate} className="mt-4 space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-[13px] font-medium text-ink dark:text-night-ink">Subject line</span>
              <input
                value={tpl.subject_template || ''}
                onChange={(e) => setTpl({ ...tpl, subject_template: e.target.value })}
                placeholder="Complete your onboarding for {company_name}"
                className={inputCls}
              />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-[13px] font-medium text-ink dark:text-night-ink">Greeting / intro paragraph</span>
              <textarea
                rows={3}
                value={tpl.body_intro || ''}
                onChange={(e) => setTpl({ ...tpl, body_intro: e.target.value })}
                placeholder="Hello, you have been invited to complete onboarding…"
                className="w-full rounded-lg border border-border dark:border-night-line bg-surface dark:bg-night-surface px-3 py-2 text-[13.5px] text-ink dark:text-night-ink placeholder:text-ink-faint focus:border-brand dark:focus:border-brand-night focus:outline-none"
              />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-[13px] font-medium text-ink dark:text-night-ink">Extra instructions (optional)</span>
              <textarea
                rows={2}
                value={tpl.extra_instructions || ''}
                onChange={(e) => setTpl({ ...tpl, extra_instructions: e.target.value })}
                placeholder="e.g. Please use your legal name as shown on your ID."
                className="w-full rounded-lg border border-border dark:border-night-line bg-surface dark:bg-night-surface px-3 py-2 text-[13.5px] text-ink dark:text-night-ink placeholder:text-ink-faint focus:border-brand dark:focus:border-brand-night focus:outline-none"
              />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-[13px] font-medium text-ink dark:text-night-ink">Closing line (optional)</span>
              <input
                value={tpl.body_closing || ''}
                onChange={(e) => setTpl({ ...tpl, body_closing: e.target.value })}
                placeholder="We look forward to working with you!"
                className={inputCls}
              />
            </label>

            <div className="flex items-center justify-between border-t border-border-soft dark:border-night-line-soft pt-4">
              <Button type="button" variant="ghost" size="sm" onClick={resetTemplate}>Reset to defaults</Button>
              <Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save template'}</Button>
            </div>
          </form>
        </Card>

        <p className="mt-4 text-xs text-ink-faint dark:text-night-ink-faint">
          Need the Resend key itself changed? That's a deployment setting — see
          RESEND_API_KEY / EMAIL_FROM in <code className="font-mono">backend/.env</code>
          {' '}(managed by your administrator; this UI intentionally cannot edit it).
        </p>
      </div>
    </div>
  )
}
