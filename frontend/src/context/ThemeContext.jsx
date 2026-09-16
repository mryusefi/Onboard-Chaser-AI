// Part D — ThemeContext: dark / light / follow-system theme.
//
//  - Mode ('light' | 'dark' | 'system') persists in localStorage
//    ('oca_theme'). 'system' follows prefers-color-scheme live.
//  - The `dark` class is toggled on <html> (Tailwind darkMode:'class').
//  - index.html carries a tiny pre-paint inline script that applies the
//    stored theme before React mounts, so a dark-mode user never sees a
//    white flash.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

const ThemeContext = createContext(null)
const STORAGE_KEY = '***'

function readStored() {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v === 'light' || v === 'dark' || v === 'system' ? v : 'system'
  } catch {
    return 'system'
  }
}

function systemPrefersDark() {
  return typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
}

function applyDarkClass(mode) {
  const dark = mode === 'dark' || (mode === 'system' && systemPrefersDark())
  document.documentElement.classList.toggle('dark', dark)
}

export function ThemeProvider({ children }) {
  const [mode, setModeState] = useState(readStored)

  useEffect(() => {
    applyDarkClass(mode)
    try {
      localStorage.setItem(STORAGE_KEY, mode)
    } catch {
      /* private mode / storage disabled — theme just won't persist */
    }
    // When following the OS, react to live preference changes.
    if (mode !== 'system' || typeof window.matchMedia !== 'function') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => applyDarkClass('system')
    mq.addEventListener ? mq.addEventListener('change', onChange) : mq.addListener(onChange)
    return () => {
      mq.removeEventListener ? mq.removeEventListener('change', onChange) : mq.removeListener(onChange)
    }
  }, [mode])

  const setMode = useCallback((m) => setModeState(m), [])
  // Cycle: anything explicit -> dark -> light -> back to system on next toggle.
  const toggle = useCallback(() => {
    setModeState((m) => {
      if (m === 'system') return systemPrefersDark() ? 'light' : 'dark'
      return m === 'dark' ? 'light' : 'dark'
    })
  }, [])

  const value = useMemo(
    () => ({ mode, isDark: mode === 'dark' || (mode === 'system' && systemPrefersDark()), setMode, toggle }),
    [mode, setMode, toggle]
  )
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
