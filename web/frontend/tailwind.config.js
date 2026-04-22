/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
        bull: {
          500: '#10b981',
          600: '#059669',
        },
        bear: {
          500: '#ef4444',
          600: '#dc2626',
        },
      },
    },
  },
  plugins: [],
}
