"use client";

import { useEffect, useState } from "react";

import { useProteomes } from "@/features/taxonomy/hooks/use-proteomes";
import { Input } from "@/shared/components/ui/input";

interface ProteomeOption {
  id: string;
  uniprot_proteome_id: string;
  organism_name?: string | null;
  strain_name?: string | null;
}

interface ProteomeComboboxProps {
  onSelect: (proteomeId: string, label: string) => void;
  placeholder?: string;
}

/** "UP000001584 — Mycobacterium tuberculosis (ATCC 25618 / H37Rv)", strain part omitted when there isn't one. */
function proteomeLabel(p: ProteomeOption): string {
  const organism = p.organism_name ?? "Unknown organism";
  const strain = p.strain_name ? ` (${p.strain_name})` : "";
  return `${p.uniprot_proteome_id} — ${organism}${strain}`;
}

export function ProteomeCombobox({ onSelect, placeholder }: ProteomeComboboxProps) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const id = setTimeout(() => setDebounced(query.trim()), 300);
    return () => clearTimeout(id);
  }, [query]);

  function handleChange(raw: string) {
    setQuery(raw);
    setOpen(true);
    // Editing the search text invalidates any committed pick: clear the parent's
    // bound value until the user selects a result again. Without this the form
    // keeps a stale selection with no UI affordance to undo it.
    onSelect("", "");
  }

  // ponytail: the proteome catalog is curated reference data (a handful of
  // rows today, unlike genes/proteins), and /api/v1/proteomes has no
  // free-text search param to debounce a query against — so this fetches one
  // page (the default limit) and filters client-side, same shortcut the
  // organism/strain Select pickers already take (see
  // features/taxonomy/types/index.ts's TAXON_FILTER_PAGE_SIZE comment).
  // Upgrade path if the catalog ever grows past one page: a backend
  // free-text filter on ListProteomesQuery.
  const { data, isLoading } = useProteomes();
  const items = (data?.items ?? []).filter((p) => {
    if (!debounced) return true;
    return proteomeLabel(p).toLowerCase().includes(debounced.toLowerCase());
  });

  function pick(id: string, label: string) {
    onSelect(id, label);
    setQuery(label);
    setOpen(false);
  }

  return (
    <div className="relative">
      <Input
        value={query}
        placeholder={placeholder ?? "Search proteomes…"}
        onChange={(e) => handleChange(e.target.value)}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false);
        }}
        role="combobox"
        aria-expanded={open}
        autoComplete="off"
      />
      {open && (
        <ul className="absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-md border bg-popover py-1 text-popover-foreground shadow-md">
          {isLoading && <li className="px-3 py-2 text-sm text-muted-foreground">Searching…</li>}
          {!isLoading && items.length === 0 && (
            <li className="px-3 py-2 text-sm text-muted-foreground">No proteomes found</li>
          )}
          {items.map((p) => {
            const label = proteomeLabel(p);
            return (
              <li key={p.id}>
                <button
                  type="button"
                  className="w-full px-3 py-2 text-left text-sm hover:bg-accent"
                  onClick={() => pick(p.id, label)}
                >
                  {label}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
