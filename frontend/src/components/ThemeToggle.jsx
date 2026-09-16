import { Sun, Moon, MonitorSmartphone } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'

// Part D — theme control cycling system → dark → light.
// Compact icon button for the Topbar / portal header.
export default function ThemeToggle({ className = '' }) {
  const { mode, isDark, setMode } = useTheme()

  function cycle() {
    // system -> opposite of the current appearance; dark -> light -> system.
    if (mode === 'system') setMode(isDark ? 'light' : 'dark')
    else if (mode === 'dark') setMode('light')
    else setMode('system')
  }

  const title =
    mode === 'system'
      ? `Theme: follow system (currently ${isDark ? 'dark' : 'light'}) — click for dark`
      : mode === 'dark'
      ? 'Theme: dark — click for light'
      : 'Theme: light — click to follow system'

  const Icon = mode === 'system' ? MonitorSmartphone : isDark ? Moon : Sun

  return (
    <button
      type="button"
      onClick={cycle}
      title={title}
      aria-label={title}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border dark:border-night-line bg-surface dark:bg-night-surface text-ink-soft dark:text-night-ink-soft transition-colors hover:bg-surface-sunken dark:hover:bg-night-sunken hover:text-ink dark:hover:text-night-ink ${className}`}
    >
      <Icon className="h-4 w-4" />
    </button>
  )
}
