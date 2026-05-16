import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    // Allow Google profile pictures returned by OAuth.
    // Without this, <Image src="https://lh3.googleusercontent.com/..."> errors:
    //   "Invalid src prop ... hostname is not configured."
    remotePatterns: [
      {
        protocol: "https",
        hostname: "lh3.googleusercontent.com",
      },
    ],
  },
};

export default nextConfig;
