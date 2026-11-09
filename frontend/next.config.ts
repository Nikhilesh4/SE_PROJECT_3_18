import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pin the workspace root to this folder. Without it Next walks up to any stray
  // package-lock.json in a parent directory and then can't resolve node_modules.
  turbopack: { root: path.resolve(__dirname) },
};

export default nextConfig;
