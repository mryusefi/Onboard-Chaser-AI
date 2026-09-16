export default function Card({ as: Comp = 'div', className = '', children, ...props }) {
  return (
    <Comp
      className={`rounded-2xl border border-border bg-surface shadow-card ${className}`}
      {...props}
    >
      {children}
    </Comp>
  )
}
