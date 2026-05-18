/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "app.digitalisglobal.com",
        pathname: "/**"
      }
    ]
  }
};

export default nextConfig;
