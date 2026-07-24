import path from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";

// @structflo/components is consumed by a cross-repo `link:` (../../structflo-components) whose
// real path escapes this app's project root. Turbopack won't resolve a symlink
// outside the root, so widen the root to the shared workspace parent. Removed once
// the package is published and installed from npm.
const workspaceRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: ["@structflo/components"],
  turbopack: {
    root: workspaceRoot,
  },
};

export default nextConfig;
