// Contract check for @structflo/daikon-ui. Mirrors daikon-design-tokens'
// contract test: it must fail the build if the public surface breaks, so a
// broken subpath or a dropped export can never be published.
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const pkg = JSON.parse(readFileSync(resolve(root, "package.json"), "utf8"));
const errors = [];

// 1. Every path in the exports map resolves to a real file on disk.
for (const [sub, target] of Object.entries(pkg.exports)) {
  if (!existsSync(resolve(root, target))) errors.push(`exports "${sub}" -> missing ${target}`);
}

// 2. The public surface actually re-exports the names consumers import.
const index = readFileSync(resolve(root, "src/target-biology/index.ts"), "utf8");
const required = [
  "EssentialityCallScale",
  "VulnerabilityPanel",
  "ResistanceLollipop",
  "EssentialityLike",
  "VulnerabilityLike",
  "MutationLike",
  "essentialityBucket",
  "ESSENTIALITY_STYLE",
];
for (const name of required) {
  if (!index.includes(name)) errors.push(`src/target-biology/index.ts does not export ${name}`);
}

if (errors.length) {
  console.error("contract FAILED:\n  " + errors.join("\n  "));
  process.exit(1);
}
console.log(
  `contract OK: ${Object.keys(pkg.exports).length} subpath(s), ${required.length} exports present`,
);
