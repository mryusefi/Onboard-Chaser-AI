export default function Card({ as: Comp = 'div', className = '', children, ...props }) {
  return (
    <Comp
      className={`rounded-2xl border border-border dark:border-night-line bg-surface dark:bg-night-surface shadow-card ${className}`}
      {...props}
    >
      {children}
    </Comp>
  )
}
