/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        harvex: {
          50: '#f2f9f4',
          100: '#e1f2e6',
          200: '#c4e5cf',
          300: '#97d1ac',
          400: '#64b583',
          500: '#3f9862',
          600: '#2f7b4e',
          700: '#27623f',
          800: '#224e34',
          900: '#1d412d',
          950: '#0c2317',
        },
        earth: {
          50: '#faf8f5',
          100: '#f4f0e9',
          200: '#e7ddce',
          300: '#d5c4ac',
          400: '#be9f83',
          500: '#ab8163',
          600: '#986d52',
          700: '#7c5743',
          800: '#66483a',
          900: '#553c33',
        }
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"SF Pro Text"',
          '"SF Pro Display"',
          'system-ui',
          'sans-serif'
        ],
      },
      boxShadow: {
        'subtle': '0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px 0 rgba(0, 0, 0, 0.02)',
        'apple': '0 4px 20px -2px rgba(0, 0, 0, 0.05), 0 2px 6px -1px rgba(0, 0, 0, 0.02)',
        'apple-hover': '0 10px 25px -4px rgba(0, 0, 0, 0.08), 0 4px 10px -2px rgba(0, 0, 0, 0.04)',
      }
    },
  },
  plugins: [],
}
