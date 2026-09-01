/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Dockerfile.prod copies .next/standalone into the runtime image -- that
  // directory only exists when this is set (without it, `next build`
  // never produces it and the Dockerfile's COPY step fails outright).
  output: 'standalone',
  images: {
    domains: [],
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;