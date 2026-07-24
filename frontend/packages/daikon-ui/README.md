# @structflo/daikon-ui

Shared presentational visualizations for the DAIKON app suite. Components take
plain data via props and render — no data fetching, no auth, no stores. Colors
are semantic Tailwind classes (`fill-chart-1`, `text-muted-foreground`, …) that
resolve through `@structflo/daikon-design-tokens` in the host app, so a chart
inherits whichever app's theme it renders in.

## Exports

- `@structflo/daikon-ui/target-biology` — `EssentialityCallScale`,
  `VulnerabilityPanel`, `ResistanceLollipop`, plus the `*Like` prop types and the
  `essentialityBucket` / `ESSENTIALITY_STYLE` helpers.

Props are typed against hand-written `*Like` interfaces, not any app's generated
API DTOs. Map your data into that shape before passing it.

## Consuming

The package ships raw `.tsx` — no build step. Each Next app must:

1. depend on it (`workspace:*` in-repo, `link:…`/`^0.1.0` cross-repo)
2. add `transpilePackages: ["@structflo/daikon-ui"]` to `next.config.ts`
3. add `@source "../node_modules/@structflo/daikon-ui/src";` to the Tailwind
   entry CSS — **Tailwind v4 does not scan `node_modules`, so without this every
   class in the package is silently dropped and the charts render unstyled.**

## Peers & deps

Peers: `react`, `react-dom` (^19). Runtime deps: `clsx`, `tailwind-merge` (for
`cn`) — both already present in every suite app.

## Publishing (deferred)

Currently consumed by file/workspace reference. To publish: `npm run test`
(contract check), then `npm publish`. A tagged CI workflow gets added when the
package moves to its own repo.
