/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/foundry/:path*",
        destination: `${process.env.NEXT_PUBLIC_FOUNDRY_API_URL || "http://localhost:8001"}/:path*`,
      },
      {
        source: "/api/assistant/:path*",
        destination: `${process.env.NEXT_PUBLIC_ASSISTANT_API_URL || "http://localhost:8002"}/api/assistant/:path*`,
      },
    ];
  },
};

export default nextConfig;
