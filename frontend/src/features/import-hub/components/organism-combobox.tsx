"use client";

import { useRef, useState } from "react";

import { useOrganisms } from "@/features/taxonomy/hooks/use-organisms";
import { Input } from "@/shared/components/ui/input";

interface OrganismComboboxProps {
  onSelect: (organismId: string, label: string) => void;
  placeholder?: string;
}

export function OrganismCombobox({ onSelect, placeholder }: OrganismComboboxProps) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleChange(raw: string) {
    setQuery(raw);
    setOpen(true);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebounced(raw.trim()), 300);
  }

  const { data, isLoading } = useOrganisms({ name: debounced || undefined });
  const items = data?.items ?? [];

  function pick(id: string, label: string) {
    onSelect(id, label);
    setQuery(label);
    setOpen(false);
  }

  return (
    <div className="relative">
      <Input
        value={query}
        placeholder={placeholder ?? "Search organisms…"}
        onChange={(e) => handleChange(e.target.value)}
        onFocus={() => setOpen(true)}
        role="combobox"
        aria-expanded={open}
        autoComplete="off"
      />
      {open && (
        <ul className="absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-md border bg-popover py-1 text-popover-foreground shadow-md">
          {isLoading && <li className="px-3 py-2 text-sm text-muted-foreground">Searching…</li>}
          {!isLoading && items.length === 0 && (
            <li className="px-3 py-2 text-sm text-muted-foreground">No organisms found</li>
          )}
          {items.map((org) => {
            const label = `${org.scientific_name}${org.ncbi_tax_id ? ` — ${org.ncbi_tax_id}` : ""}`;
            return (
              <li key={org.id}>
                <button
                  type="button"
                  className="w-full px-3 py-2 text-left text-sm hover:bg-accent"
                  onClick={() => pick(org.id, label)}
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
