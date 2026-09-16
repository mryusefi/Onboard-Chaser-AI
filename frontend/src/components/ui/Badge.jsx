import { CheckCircle2, AlertTriangle, Clock, CircleDot, ShieldCheck, XCircle, Mail, Ban } from 'lucide-react'

// US12-frontend: extended status palette.
// Old prototype statuses (complete/attention/overdue/pending/sent/scheduled)
// + real backend statuses: onboarding status, invitation_email_status (US07),
// verification_status (US11), needs_attention (US10), reminder status (US08).
const STATUS_CONFIG = {
  // Onboarding / document status
  complete: { label: 'Complete', bg: 'bg-success-soft', text: 'text-success', Icon: CheckCircle2 },
  completed: { label: 'Completed', bg: 'bg-success-soft', text: 'text-success', Icon: CheckCircle2 },
  uploaded: { label: 'Uploaded', bg: 'bg-success-soft', text: 'text-success', Icon: CheckCircle2 },
  attention: { label: 'Needs attention', bg: 'bg-warning-soft', text: 'text-warning', Icon: AlertTriangle },
  in_progress: { label: 'In progress', bg: 'bg-brand-soft', text: 'text-brand-dark', Icon: CircleDot },
  pending: { label: 'Pending', bg: 'bg-neutral-soft', text: 'text-neutral', Icon: CircleDot },
  missing: { label: 'Missing', bg: 'bg-danger-soft', text: 'text-danger', Icon: AlertTriangle },
  // Verification (US11)
  unverified: { label: 'Unverified', bg: 'bg-neutral-soft', text: 'text-neutral', Icon: CircleDot },
  verified: { label: 'Verified', bg: 'bg-success-soft', text: 'text-success', Icon: ShieldCheck },
  rejected: { label: 'Rejected', bg: 'bg-danger-soft', text: 'text-danger', Icon: XCircle },
  // Invitation email status (US07)
  not_sent: { label: 'Not sent', bg: 'bg-neutral-soft', text: 'text-neutral', Icon: Ban },
  sent: { label: 'Sent', bg: 'bg-success-soft', text: 'text-success', Icon: Mail },
  failed: { label: 'Failed', bg: 'bg-danger-soft', text: 'text-danger', Icon: AlertTriangle },
  delivered: { label: 'Delivered', bg: 'bg-success-soft', text: 'text-success', Icon: Mail },
  bounced: { label: 'Bounced', bg: 'bg-danger-soft', text: 'text-danger', Icon: AlertTriangle },
  // Reminder attempt status (US08)
  scheduled: { label: 'Scheduled', bg: 'bg-neutral-soft', text: 'text-neutral', Icon: Clock },
  skipped: { label: 'Skipped', bg: 'bg-neutral-soft', text: 'text-neutral', Icon: Clock },
}

export default function Badge({ status, children, withIcon = true, className = '' }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending
  const Icon = config.Icon
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${config.bg} ${config.text} ${className}`}
    >
      {withIcon ? <Icon className="h-3.5 w-3.5" /> : null}
      {children || config.label}
    </span>
  )
}
