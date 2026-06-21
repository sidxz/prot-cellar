"use client";

import { useEffect, useRef, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { cn } from "@/shared/lib/utils";

import { type StructureRef, structures } from "../../lib/protein-annotations";
import type { Protein } from "../../types";

const MOLSTAR_VERSION = "3.3.0";
const MOLSTAR_JS = `https://cdn.jsdelivr.net/npm/pdbe-molstar@${MOLSTAR_VERSION}/build/pdbe-molstar-component.js`;
const MOLSTAR_CSS = `https://cdn.jsdelivr.net/npm/pdbe-molstar@${MOLSTAR_VERSION}/build/pdbe-molstar.css`;

let molstarPromise: Promise<void> | null = null;

/** Inject the pdbe-molstar web component bundle once; resolves when registered. */
function loadMolstar(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.customElements?.get("pdbe-molstar")) return Promise.resolve();
  if (molstarPromise) return molstarPromise;
  molstarPromise = new Promise<void>((resolve, reject) => {
    if (!document.querySelector("link[data-molstar]")) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = MOLSTAR_CSS;
      link.dataset.molstar = "1";
      document.head.appendChild(link);
    }
    const script = document.createElement("script");
    script.src = MOLSTAR_JS;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load pdbe-molstar"));
    document.body.appendChild(script);
  });
  return molstarPromise;
}

interface ViewerStructure extends StructureRef {
  kind: "pdb" | "alphafold";
  label: string;
}

/** AlphaFold model-file versions vary per entry, so resolve the real URL from the API. */
async function resolveAlphaFoldUrl(accession: string): Promise<string | undefined> {
  try {
    const res = await fetch(`https://alphafold.ebi.ac.uk/api/prediction/${accession}`);
    if (!res.ok) return undefined;
    const data = (await res.json()) as Array<{ cifUrl?: string }>;
    return data[0]?.cifUrl;
  } catch {
    return undefined;
  }
}

function MolstarViewer({ structure }: { structure: ViewerStructure }) {
  const ref = useRef<HTMLDivElement>(null);
  const { id, kind } = structure;

  useEffect(() => {
    let cancelled = false;

    async function init() {
      const customDataUrl = kind === "alphafold" ? await resolveAlphaFoldUrl(id) : undefined;
      // AlphaFold selected but URL unresolved → leave blank; the link-out still works.
      if (kind === "alphafold" && !customDataUrl) return;

      await loadMolstar();
      const host = ref.current;
      if (cancelled || !host) return;
      host.replaceChildren();

      const el = document.createElement("pdbe-molstar");
      if (customDataUrl) {
        el.setAttribute("custom-data-url", customDataUrl);
        el.setAttribute("custom-data-format", "cif");
        el.setAttribute("alphafold-view", "true");
      } else {
        el.setAttribute("molecule-id", id.toLowerCase());
      }
      el.setAttribute("hide-controls", "true");
      // Mol* lays its canvas out as position:absolute inset:0 — fill the
      // (position:relative) host so it never escapes to the viewport.
      el.style.position = "absolute";
      el.style.top = "0";
      el.style.left = "0";
      el.style.width = "100%";
      el.style.height = "100%";
      host.appendChild(el);
    }

    init().catch(() => {
      /* viewer stays blank; the link-out below remains usable */
    });
    return () => {
      cancelled = true;
    };
  }, [id, kind]);

  return (
    <div
      ref={ref}
      data-structure-id={id}
      className="relative h-[360px] w-full overflow-hidden rounded-md border border-border bg-white"
    />
  );
}

function structureLink(s: ViewerStructure): string {
  return s.kind === "pdb"
    ? `https://www.ebi.ac.uk/pdbe/entry/pdb/${s.id.toLowerCase()}`
    : `https://alphafold.ebi.ac.uk/entry/${s.id}`;
}

export function StructureViewerCard({ protein }: { protein: Protein }) {
  const { pdb, alphafold } = structures(protein);
  const options: ViewerStructure[] = [
    ...pdb.map((s) => ({ ...s, kind: "pdb" as const, label: `PDB ${s.id.toUpperCase()}` })),
    ...alphafold.map((s) => ({ ...s, kind: "alphafold" as const, label: `AlphaFold ${s.id}` })),
  ];
  const [selectedId, setSelectedId] = useState(options[0]?.id ?? "");

  if (options.length === 0) return null;
  const selected = options.find((o) => o.id === selectedId) ?? options[0];

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">3D Structure</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {options.length > 1 && (
          <div className="flex flex-wrap gap-1">
            {options.map((o) => (
              <button
                key={o.id}
                type="button"
                onClick={() => setSelectedId(o.id)}
                className={cn(
                  "rounded border px-2 py-0.5 text-xs transition-colors",
                  o.id === selected.id
                    ? "border-primary text-primary"
                    : "border-border text-muted-foreground hover:text-foreground",
                )}
              >
                {o.label}
              </button>
            ))}
          </div>
        )}
        <MolstarViewer structure={selected} />
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {selected.method && <span>{selected.method}</span>}
          {selected.resolution && <span>{selected.resolution}</span>}
          <a
            href={structureLink(selected)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            {selected.kind === "pdb" ? "View on PDBe" : "View on AlphaFold"} ↗
          </a>
        </div>
      </CardContent>
    </Card>
  );
}
