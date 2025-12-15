/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: true,
    // Ensure environment variables are available
    env: {
        NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
        NEXT_PUBLIC_FUNCTION_KEY: process.env.NEXT_PUBLIC_FUNCTION_KEY,
    },
}

module.exports = nextConfig
