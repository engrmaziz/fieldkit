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
      {
        source: "/api/tracehub/:path*",
        destination: `${process.env.NEXT_PUBLIC_TRACEHUB_API_URL || "http://localhost:8006"}/:path*`,
      },
      {
        source: "/api/docai/:path*",
        destination: `${process.env.NEXT_PUBLIC_DOCAI_API_URL || "http://localhost:8004"}/:path*`,
      },
      {
        source: "/api/inspect/:path*",
        destination: `${process.env.NEXT_PUBLIC_VISION_API_URL || "http://localhost:8005"}/inspect/:path*`,
      },
      {
        source: "/api/workflows/:path*",
        destination: `${process.env.NEXT_PUBLIC_WORKFLOW_API_URL || "http://localhost:8008"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
