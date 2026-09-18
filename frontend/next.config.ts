import type { NextConfig } from "next";

/**
 * Extra hostnames allowed to load the dev server's assets.
 *
 * `getUserMedia` only works in a secure context (https:// or localhost), so
 * testing the vendor camera flow on a real phone means either an HTTPS tunnel
 * or hitting the dev server over the LAN. This env var covers the browser
 * assets case; the camera still needs HTTPS or localhost.
 *
 *   NEXT_ALLOWED_DEV_ORIGINS="192.168.1.5,my-laptop.local"
 */
const allowedDevOrigins = (process.env.NEXT_ALLOWED_DEV_ORIGINS ?? "")
  .split(",")
  .map((origin) => origin.trim())
  .filter(Boolean);

const nextConfig: NextConfig = {
  ...(allowedDevOrigins.length ? { allowedDevOrigins } : {}),
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/api/:path*', // Proxy to Backend
      },
      {
        source: '/uploads/:path*',
        destination: 'http://127.0.0.1:8000/uploads/:path*', // Proxy uploads too
      }
    ];
  },
};

export default nextConfig;
