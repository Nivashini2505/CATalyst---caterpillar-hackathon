/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        cat: { yellow: '#FFCD11', soft: '#FFD84D', dark: '#111315' },
        ink: {
          50: '#EAECEF', 100: '#C7CCD4', 200: '#8A93A1', 300: '#5B6472',
          400: '#3A3F47', 500: '#26292E', 600: '#1B1D20', 700: '#141618', 900: '#0C0D0F',
        },
        ok: '#22C55E', warn: '#F59E0B', crit: '#EF4444', info: '#3B82F6',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'Segoe UI', 'sans-serif'],
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(255,205,17,0.25), 0 8px 30px rgba(255,205,17,0.08)',
        card: '0 1px 2px rgba(0,0,0,0.4), 0 8px 24px rgba(0,0,0,0.25)',
      },
      keyframes: {
        'pulse-soft': { '0%,100%': { opacity: '1' }, '50%': { opacity: '0.55' } },
      },
      animation: { 'pulse-soft': 'pulse-soft 2.4s ease-in-out infinite' },
    },
  },
  plugins: [],
};
