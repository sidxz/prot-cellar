# Task 4 Report: List Column Definitions (`import-columns.tsx`)

## Summary
Successfully implemented the ag-grid column definitions for the import list table with status/type badge cell renderers, date formatting, and target link navigation. TDD approach: test first, verify RED, implement, verify GREEN, commit.

## Files Created
- `frontend/src/features/import-hub/components/import-columns.tsx` (81 lines)
- `frontend/src/features/import-hub/components/import-columns.test.tsx` (54 lines)

## Implementation Details
- **Column definitions** (`importColumnDefs`): 5 columns (Target, Type, Status, Created, Finished) with flex/width, sortable flags, and cell renderers
- **TargetCell**: Renders as a styled Next.js Link to `/admin/imports/${id}`
- **TypeCell**: Renders `IMPORT_TYPE_LABELS` with secondary Badge variant
- **StatusCell**: Renders status text with `STATUS_VARIANTS` colored Badge
- **DateCell**: Formats ISO 8601 dates with `toLocaleString()`, displays "—" for null

## TDD Evidence

### RED (Test Fails)
```bash
$ cd /Users/sidx/workspace/prot-cellar/frontend && ./node_modules/.bin/vitest run src/features/import-hub/components/import-columns.test.tsx
```
Output: `Error: Failed to resolve import "./import-columns"` — file does not exist ✓

### GREEN (Test Passes)
```bash
$ cd /Users/sidx/workspace/prot-cellar/frontend && ./node_modules/.bin/vitest run src/features/import-hub/components/import-columns.test.tsx
```
Output:
```
 ✓ src/features/import-hub/components/import-columns.test.tsx (2 tests) 20ms
 Test Files  1 passed (1)
 Tests  2 passed (2)
```

### Test Coverage
1. ✓ Status cell renders raw status text ("succeeded")
2. ✓ Type cell renders human label from IMPORT_TYPE_LABELS ("Proteome")

## Commit
```
8ff2b14 feat(imports): import list column defs with status/type badges
```

## Files Changed
- Created: `frontend/src/features/import-hub/components/import-columns.tsx`
- Created: `frontend/src/features/import-hub/components/import-columns.test.tsx`

## Dependencies Verified
- ✓ `ImportRun`, `IMPORT_TYPE_LABELS`, `STATUS_VARIANTS` imported from `../types` (Task 2)
- ✓ `Badge` imported from `@/shared/components/ui/badge`
- ✓ `ColDef`, `ICellRendererParams` from `ag-grid-community`
- ✓ `Link` from `next/link`
