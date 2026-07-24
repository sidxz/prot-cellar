import path from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";

// Parent dir that holds the structflo-components checkout. Turbopack needs it
// as module root while @structflo/components is pnpm-linked (dev only — prod
// builds install from npm, and widening the root would shift standalone
// output tracing).
const workspaceRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: ["@structflo/components"],
  ...(process.env.NODE_ENV !== "production" && {
    turbopack: { root: workspaceRoot },
  }),
};

export default nextConfig;
