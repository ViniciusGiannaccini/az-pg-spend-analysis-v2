/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
        './src/components/**/*.{js,ts,jsx,tsx,mdx}',
        './src/app/**/*.{js,ts,jsx,tsx,mdx}',
    ],
    theme: {
        extend: {
            colors: {
                primary: {
                    50: '#f0f4ff', // Very light blue
                    100: '#dbeafe',
                    200: '#bfdbfe', // Light blue (was purple-ish)
                    300: '#93c5fd', // Soft blue
                    400: '#60a5fa', // Bright blue accent
                    500: '#3b82f6', // Standard blue
                    600: '#2563eb', // Deep blue
                    700: '#1d4ed8',
                    800: '#1c0957', // Main Brand Color (Dark Navy)
                    900: '#0e0330', // Deepest background
                },
            },
        },
    },
    plugins: [],
}
