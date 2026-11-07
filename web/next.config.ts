import type { NextConfig } from "next";

// The browser talks to /api on the same origin; Next forwards it to FastAPI, so the session cookie just works.
const API = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};

export default nextConfig;
