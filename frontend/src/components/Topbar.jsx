import ThemeToggle from './ThemeToggle'

export default function Topbar({ eyebrow, title, subtitle, actions }) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4 border-b border-border-soft dark:border-night-line-soft px-8 py-6">
      <div>
        {eyebrow ? (
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-faint dark:text-night-ink-faint">{eyebrow}</p>
        ) : null}
        <h1 className="font-display text-[22px] font-semibold tracking-tight text-ink dark:text-night-ink">{title}</h1>
        {subtitle ? <p className="mt-1 text-sm text-ink-soft dark:text-night-ink-soft">{subtitle}</p> : null}
      </div>
      {/* Part D: theme toggle sits beside page actions on every HR page */}
      <div className="flex shrink-0 items-center gap-2.5">
        {actions}
        <ThemeToggle />
      </div>
    </header>
  )
}
