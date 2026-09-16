/** @type {import('tailwindcss').Config} */
// US12-frontend — design tokens translated from the prepared UI kit's
// Tailwind v4 `@theme` block into v3 config (the project pins tailwindcss 3.4).
// Class names stay identical: bg-paper, bg-surface, bg-surface-sunken,
// text-ink / -soft / -faint, border-border / -soft, bg-brand / text-brand-dark,
// bg-brand-soft, bg-success-soft + text-success (likewise warning/danger/
// neutral), bg-navy, shadow-card, shadow-pop, font-display.
//
// Part D — dark mode (Tailwind `darkMode: 'class'`). Strategy: the LIGHT
// tokens are never redefined; instead each component layer adds `dark:`
// variants that reference a parallel `night` surface scale plus `*-night`
// shades on the semantic colors (class order stays readable, and nothing
// changes if JS is off — no dark class, pure light UI):
//   surfaces:  bg-paper dark:bg-night · bg-surface dark:bg-night-surface
//              bg-surface-sunken dark:bg-night-sunken · border-border dark:border-night-line
//   text:      text-ink dark:text-night-ink · -soft · -faint
//   accents:   text-success dark:text-success-night · badges
//              dark:bg-success-night-soft with dark:text-success-night etc.
//              (night tones are desaturated/brightened so badges keep ≥4.5:1
//              contrast against their dark-soft backgrounds)
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        paper: '#FAFAF8',
        surface: { DEFAULT: '#FFFFFF', sunken: '#F1F1EE' },
        ink: { DEFAULT: '#14171F', soft: '#565B66', faint: '#9498A2' },
        border: { DEFAULT: '#E5E4DE', soft: '#EEEDE8' },
        brand: { DEFAULT: '#0B6E6E', dark: '#084F4F', soft: '#E4F1EF' },
        navy: '#14213D',
        success: { DEFAULT: '#1E7A46', soft: '#E4F3EA' },
        warning: { DEFAULT: '#A15C07', soft: '#FBF0DD' },
        danger: { DEFAULT: '#B23A3A', soft: '#FBEAEA' },
        neutral: { DEFAULT: '#5B5F6B', soft: '#ECECE8' },

        // Dark-mode surfaces (Part D).
        night: {
          DEFAULT: '#0F1218',       // page background (near-ink, not pure black)
          surface: '#171B23',        // cards, inputs
          sunken: '#1F242E',         // wells, table headers/rows
          line: '#2A2F3A',           // borders
          'line-soft': '#22262F',    // hairline borders
          ink: '#E7E7E3',            // primary text
          'ink-soft': '#A6ABB5',
          'ink-faint': '#6E737E',
        },
        // Brightened/desaturated semantic shades for dark mode (badge text +
        // icon/heading accents).
        'brand-night': '#4FB3AA',
        'success-night': '#5FCFC0',
        'warning-night': '#E8B564',
        'danger-night': '#F08A8A',
        'neutral-night': '#A6ABB5',
        // Dark badge backgrounds.
        'brand-night-soft': '#123536',
        'success-night-soft': '#123028',
        'warning-night-soft': '#33260F',
        'danger-night-soft': '#3A1A1A',
        'neutral-night-soft': '#2A2F3A',
        'navy-night': '#3D4A6B',

        // Legacy primary palette (kept until fully unused; old pages removed).
        primary: {
          50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 300: '#93c5fd',
          400: '#60a5fa', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8',
          800: '#1e40af', 900: '#1e3a8a',
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'Inter', 'sans-serif'],
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(20, 23, 31, 0.04), 0 1px 1px rgba(20, 23, 31, 0.03)',
        pop: '0 12px 32px rgba(20, 23, 31, 0.12), 0 2px 8px rgba(20, 23, 31, 0.06)',
      },
    },
  },
  plugins: [],
}
