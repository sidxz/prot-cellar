import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: ["@structflo/daikon-ui"],
};

export default nextConfig;
