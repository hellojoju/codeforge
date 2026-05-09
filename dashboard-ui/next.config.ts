import type { NextConfig } from "next"
import path from "path"

const BACKEND_PORT = 18753

const nextConfig: NextConfig = {
  devIndicators: false,
  turbopack: {
    root: path.resolve(__dirname),
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `http://localhost:${BACKEND_PORT}/api/:path*`,
      },
      {
        source: '/ws/:path*',
        destination: `http://localhost:${BACKEND_PORT}/ws/:path*`,
      },
    ]
  },
}

export default nextConfig
