/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/foundry/:path*",
        destination: `${process.env.NEXT_PUBLIC_FOUNDRY_API_URL || "http://localhost:8001"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
