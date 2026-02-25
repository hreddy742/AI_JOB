/** @type {import('next').NextConfig} */
const backendBase = (process.env.INTERNAL_API_BASE_URL || "http://api:8001").replace(/\/+$/, "");

const nextConfig = {
  // Isolate build artifacts per environment (e.g. host vs Docker dev) to avoid mixed chunk graphs.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  reactStrictMode: true,
  experimental: {
    typedRoutes: false
  },
  async rewrites() {
    return [
      {
        source: "/backend/:path*",
        destination: `${backendBase}/:path*`,
      },
    ];
  },
};

export default nextConfig;
