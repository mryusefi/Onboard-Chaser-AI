const VARIANTS = {
  primary:
    'bg-brand text-white hover:bg-brand-dark active:bg-brand-dark disabled:bg-neutral-soft disabled:text-ink-faint',
  secondary:
    'bg-white text-ink border border-border hover:bg-surface-sunken active:bg-surface-sunken disabled:text-ink-faint',
  ghost: 'bg-transparent text-ink-soft hover:bg-surface-sunken hover:text-ink disabled:text-ink-faint',
  danger: 'bg-danger text-white hover:opacity-90 disabled:bg-neutral-soft disabled:text-ink-faint',
  navy: 'bg-navy text-white hover:opacity-90',
}

const SIZES = {
  sm: 'h-8 px-3 text-[13px] gap-1.5',
  md: 'h-10 px-4 text-sm gap-2',
  lg: 'h-11 px-5 text-[15px] gap-2',
}

export default function Button({
  as: Comp = 'button',
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  icon: Icon,
  iconRight: IconRight,
  ...props
}) {
  return (
    <Comp
      className={`inline-flex select-none items-center justify-center whitespace-nowrap rounded-lg font-medium transition-colors duration-150 disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...props}
    >
      {Icon ? <Icon className="h-4 w-4 shrink-0" /> : null}
      {children}
      {IconRight ? <IconRight className="h-4 w-4 shrink-0" /> : null}
    </Comp>
  )
}
