import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* For Next.js 15, we enable strict mode for better debugging */
  reactStrictMode: true,
  
  /* This allows us to use images from Supabase storage later */
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**.supabase.co',
        port: '',
        pathname: '/storage/v1/object/public/**',
      },
    ],
  },
};

export default nextConfig;