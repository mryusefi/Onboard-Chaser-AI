/** @type {import('tailwindcss').Config} */
// US12-frontend — design tokens translated from the prepared UI kit's
// Tailwind v4 `@theme` block (src-new/index.css) into v3 config, since the
// project pins tailwindcss 3.4. Class names stay identical: bg-paper,
// text-ink, bg-brand, text-brand-dark, bg-brand-soft, bg-success-soft,
// text-success, bg-warning-soft, text-warning, bg-danger-soft, text-danger,
// bg-neutral-soft, text-neutral, bg-navy, border-border, bg-surface,
// bg-surface-sunken, shadow-card, shadow-pop, font-display.
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        paper: '#FAFAF8',
        surface: {
          DEFAULT: '#FFFFFF',
          sunken: '#F1F1EE',
        },
        ink: {
          DEFAULT: '#14171F',
          soft: '#565B66',
          faint: '#9498A2',
        },
        border: {
          DEFAULT: '#E5E4DE',
          soft: '#EEEDE8',
        },
        brand: {
          DEFAULT: '#0B6E6E',
          dark: '#084F4F',
          soft: '#E4F1EF',
        },
        navy: '#14213D',
        success: {
          DEFAULT: '#1E7A46',
          soft: '#E4F3EA',
        },
        warning: {
          DEFAULT: '#A15C07',
          soft: '#FBF0DD',
        },
        danger: {
          DEFAULT: '#B23A3A',
          soft: '#FBEAEA',
        },
        neutral: {
          DEFAULT: '#5B5F6B',
          soft: '#ECECE8',
        },
        // Legacy primary palette (kept until fully unused; old pages removed).
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
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
