const backendHostport = process.env.BACKEND_HOSTPORT?.trim();
const publicApiBase = process.env.NEXT_PUBLIC_API_URL?.trim() || "http://localhost:8000/api/v1";
const shouldProxyApi = Boolean(backendHostport && publicApiBase.startsWith("/"));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  compress: true,
  poweredByHeader: false,
  images: {
    formats: ["image/avif", "image/webp"],
    minimumCacheTTL: 60 * 60 * 24 * 7,
  },
  experimental: {
    optimizePackageImports: ["lucide-react"],
  },
  async rewrites() {
    if (!shouldProxyApi || !backendHostport) {
      return [];
    }

    const backendOrigin = `http://${backendHostport}`;
    return [
      {
        source: "/api/:path*",
        destination: `${backendOrigin}/api/:path*`,
      },
      {
        source: "/uploads/:path*",
        destination: `${backendOrigin}/uploads/:path*`,
      },
    ];
  },
};

export default nextConfig;
