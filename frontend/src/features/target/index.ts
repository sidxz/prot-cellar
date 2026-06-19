// Types
export type { Target, TargetComponentView, TargetComponentInput, TargetListFilters } from "./types";
export { TARGET_TYPE_LABELS, RELATIONSHIP_LABELS } from "./types";

// Hooks
export { useTargets, useTarget, useCreateTarget, useUpdateTarget } from "./hooks/use-targets";

// Cardinality utilities
export { cardinalityRule, componentCountValid, cardinalityHint } from "./lib/cardinality";

// Components
export { TargetComponentsEditor } from "./components/target-components-editor";
export { TargetFormDialog } from "./components/target-form-dialog";
export { TargetListPage } from "./components/target-list";
export { TargetDetailPage } from "./components/target-detail";
