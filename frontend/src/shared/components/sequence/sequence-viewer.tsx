"use client";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { showError } from "@/shared/lib/toast";
import { cn } from "@/shared/lib/utils";
import { useState } from "react";
import { chunkSequence, toFasta } from "./sequence";

export interface SequenceViewerProps {
  sequence: string;
  length: number;
  mass?: number;
  accession?: string;
  className?: string;
}

const RULER_STEP = 10;
const RESIDUES_PER_LINE = 60;

function buildRuler(lineStart: number, lineLen: number): string {
  let ruler = "";
  for (let i = 1; i <= lineLen; i++) {
    const pos = lineStart + i;
    if (pos % RULER_STEP === 0) {
      const label = String(pos);
      // Place label so its last digit aligns at position i
      const padStart = i - label.length;
      ruler = ruler.padEnd(padStart, " ") + label;
    }
  }
  return ruler.padEnd(lineLen, " ");
}

export function SequenceViewer({
  sequence,
  length,
  mass,
  accession,
  className,
}: SequenceViewerProps) {
  const [copied, setCopied] = useState(false);
  const chunks = chunkSequence(sequence, RESIDUES_PER_LINE);

  function handleCopy() {
    navigator.clipboard
      .writeText(sequence)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => showError("Failed to copy sequence"));
  }

  function handleDownloadFasta() {
    const header = accession ?? "sequence";
    const fasta = toFasta(header, sequence, RESIDUES_PER_LINE);
    const blob = new Blob([fasta], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${header}.fasta`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div
      className={cn("flex flex-col gap-3 rounded-lg border border-border bg-card p-4", className)}
    >
      {/* Header row */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          {accession && (
            <span className="font-mono text-sm font-semibold text-primary">{accession}</span>
          )}
          <Badge variant="outline">{length} aa</Badge>
          {mass !== undefined && <Badge variant="outline">{mass.toLocaleString()} Da</Badge>}
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleCopy}
            aria-label="Copy sequence to clipboard"
          >
            {copied ? "Copied!" : "Copy"}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleDownloadFasta}
            aria-label="Download sequence as FASTA file"
          >
            Download FASTA
          </Button>
        </div>
      </div>

      {/* Sequence block */}
      <section className="overflow-x-auto rounded-md bg-muted p-3" aria-label="Protein sequence">
        <pre className="font-mono text-xs leading-relaxed text-foreground">
          {chunks.map((chunk, idx) => {
            const lineStart = idx * RESIDUES_PER_LINE;
            const ruler = buildRuler(lineStart, chunk.length);
            return (
              <div key={lineStart} className="flex gap-2">
                {/* Position label */}
                <span
                  className="w-8 shrink-0 select-none text-right text-muted-foreground"
                  aria-hidden="true"
                >
                  {lineStart + 1}
                </span>
                {/* Sequence + ruler */}
                <span className="flex flex-col">
                  <span className="tracking-widest text-foreground">{chunk}</span>
                  <span className="select-none text-muted-foreground/60" aria-hidden="true">
                    {ruler}
                  </span>
                </span>
              </div>
            );
          })}
        </pre>
      </section>
    </div>
  );
}
