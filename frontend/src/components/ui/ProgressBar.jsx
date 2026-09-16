export default function ProgressBar({ percent = 0, size = 'md', className = '' }) {
  const height = size === 'sm' ? 'h-1.5' : size === 'lg' ? 'h-2.5' : 'h-2'
  const color = percent >= 100 ? 'bg-success' : percent < 50 ? 'bg-danger' : 'bg-brand'

  return (
    <div
      className={`w-full overflow-hidden rounded-full bg-surface-sunken ${height} ${className}`}
      role="progressbar"
      aria-valuenow={percent}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={`h-full rounded-full transition-all duration-700 ease-out ${color}`}
        style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
      />
    </div>
  )
}
