import { CheckCircle2, AlertTriangle, Clock, CircleDot, ShieldCheck, XCircle, Mail, Ban } from 'lucide-react'

// US12-frontend: extended status palette.
// Old prototype statuses (complete/attention/overdue/pending/sent/scheduled)
// + real backend statuses: onboarding status, invitation_email_status (US07),
// verification_status (US11), needs_attention (US10), reminder status (US08).
const STATUS_CONFIG = {
  // Onboarding / document status
  complete: { label: 'Complete', bg: 'bg-success-soft dark:bg-success-night-soft', text: 'text-success dark:text-success-night', Icon: CheckCircle2 },
  completed: { label: 'Completed', bg: 'bg-success-soft dark:bg-success-night-soft', text: 'text-success dark:text-success-night', Icon: CheckCircle2 },
  uploaded: { label: 'Uploaded', bg: 'bg-success-soft dark:bg-success-night-soft', text: 'text-success dark:text-success-night', Icon: CheckCircle2 },
  attention: { label: 'Needs attention', bg: 'bg-warning-soft dark:bg-warning-night-soft', text: 'text-warning dark:text-warning-night', Icon: AlertTriangle },
  in_progress: { label: 'In progress', bg: 'bg-brand-soft dark:bg-brand-night-soft', text: 'text-brand-dark dark:text-brand-night', Icon: CircleDot },
  pending: { label: 'Pending', bg: 'bg-neutral-soft dark:bg-neutral-night-soft', text: 'text-neutral dark:text-neutral-night', Icon: CircleDot },
  missing: { label: 'Missing', bg: 'bg-danger-soft dark:bg-danger-night-soft', text: 'text-danger dark:text-danger-night', Icon: AlertTriangle },
  // Verification (US11)
  unverified: { label: 'Unverified', bg: 'bg-neutral-soft dark:bg-neutral-night-soft', text: 'text-neutral dark:text-neutral-night', Icon: CircleDot },
  verified: { label: 'Verified', bg: 'bg-success-soft dark:bg-success-night-soft', text: 'text-success dark:text-success-night', Icon: ShieldCheck },
  rejected: { label: 'Rejected', bg: 'bg-danger-soft dark:bg-danger-night-soft', text: 'text-danger dark:text-danger-night', Icon: XCircle },
  // Invitation email status (US07)
  not_sent: { label: 'Not sent', bg: 'bg-neutral-soft dark:bg-neutral-night-soft', text: 'text-neutral dark:text-neutral-night', Icon: Ban },
  sent: { label: 'Sent', bg: 'bg-success-soft dark:bg-success-night-soft', text: 'text-success dark:text-success-night', Icon: Mail },
  failed: { label: 'Failed', bg: 'bg-danger-soft dark:bg-danger-night-soft', text: 'text-danger dark:text-danger-night', Icon: AlertTriangle },
  delivered: { label: 'Delivered', bg: 'bg-success-soft dark:bg-success-night-soft', text: 'text-success dark:text-success-night', Icon: Mail },
  bounced: { label: 'Bounced', bg: 'bg-danger-soft dark:bg-danger-night-soft', text: 'text-danger dark:text-danger-night', Icon: AlertTriangle },
  // Reminder attempt status (US08)
  scheduled: { label: 'Scheduled', bg: 'bg-neutral-soft dark:bg-neutral-night-soft', text: 'text-neutral dark:text-neutral-night', Icon: Clock },
  skipped: { label: 'Skipped', bg: 'bg-neutral-soft dark:bg-neutral-night-soft', text: 'text-neutral dark:text-neutral-night', Icon: Clock },
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
