import { Check, Clock } from 'lucide-react'

// The "chase trail" is the product's signature visual device: a dotted path
// with checkpoint nodes that represents the sequence of follow-ups it took
// to get a candidate to 100%. It's used for reminder history.
export default function ChaseTrail({ items }) {
  return (
    <ol className="relative">
      {items.map((item, i) => {
        const isLast = i === items.length - 1
        const done = item.status === 'sent'
        return (
          <li key={item.id || i} className="relative flex gap-3.5 pb-6 last:pb-0">
            {!isLast && (
              <span
                aria-hidden
                className="absolute left-[11px] top-6 bottom-0 w-px"
                style={{
                  backgroundImage: `linear-gradient(to bottom, #D8D7CF 0 4px, transparent 4px 8px)`,
                  backgroundSize: '1px 8px',
                }}
              />
            )}
            <span
              className={`relative z-10 mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 ${
                done
                  ? 'border-brand bg-brand text-white'
                  : item.status === 'scheduled'
                  ? 'border-dashed border-ink-faint bg-surface text-ink-faint'
                  : 'border-border bg-surface text-ink-faint'
              }`}
            >
              {done ? <Check className="h-3.5 w-3.5" /> : <Clock className="h-3 w-3" />}
            </span>
            <div className="flex-1 pt-0.5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                <p className="text-[13px] font-medium text-ink">{item.label}</p>
                <p className="font-mono text-xs text-ink-faint">{item.date}</p>
              </div>
              {item.sublabel ? <p className="mt-0.5 text-xs text-ink-soft">{item.sublabel}</p> : null}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
