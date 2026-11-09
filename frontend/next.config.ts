import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pin the workspace root to this folder. Without it Next walks up to any stray
  // package-lock.json in a parent directory and then can't resolve node_modules.
  turbopack: { root: path.resolve(__dirname) },

  poweredByHeader: false,

  async headers() {
    const security = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      // Never leak full URLs (which may carry query strings) to other sites.
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      { key: "Content-Security-Policy", value: "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'" },
      ...(process.env.NODE_ENV === "production"
        ? [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" }]
        : []),
    ];
    return [
      { source: "/:path*", headers: security },
      // Sign-in pages and the session endpoints must never be cached by the browser or a proxy.
      { source: "/(login|register)", headers: [{ key: "Cache-Control", value: "no-store" }] },
      { source: "/api/session/:path*", headers: [{ key: "Cache-Control", value: "no-store" }] },
    ];
  },
};

export default nextConfig;
