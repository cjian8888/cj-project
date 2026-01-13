/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                slate: {
                    950: '#0f172a',
                },
                // Custom accent colors
                accent: {
                    blue: '#3b82f6',
                    cyan: '#06b6d4',
                    red: '#ef4444',
                    green: '#22c55e',
                    warning: '#eab308',
                },
            },
            fontFamily: {
                sans: ['Inter', 'sans-serif'],
                mono: ['JetBrains Mono', 'monospace'],
            },
            boxShadow: {
                'glow-blue': '0 4px 15px -3px rgba(59, 130, 246, 0.4)',
                'glow-cyan': '0 6px 20px -3px rgba(6, 182, 212, 0.5)',
                'glow-green': '0 0 8px rgba(34, 197, 94, 0.5)',
                'glow-yellow': '0 0 8px rgba(234, 179, 8, 0.5)',
            },
            animation: {
                'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                'ping-slow': 'ping 2s cubic-bezier(0, 0, 0.2, 1) infinite',
            },
        },
    },
    plugins: [],
}
