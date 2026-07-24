// Public surface of the target-biology visuals. Consumers import from
// "@structflo/daikon-ui/target-biology" — never a deeper path.
export { EssentialityCallScale } from "./essentiality-call-scale";
export { VulnerabilityPanel } from "./vulnerability-panel";
export { ResistanceLollipop } from "./resistance-lollipop";

// Domain helpers shared beyond the charts (prot-cellar's genomic-context view
// reuses the fitness-axis bucketing so its legend can't drift from the scale).
export { ESSENTIALITY_STYLE, essentialityBucket } from "./essentiality";
export type { EssentialityBucket, EssentialityLike } from "./essentiality";
export type { VulnerabilityLike } from "./vulnerability";
export type { MutationLike } from "./resistance";
