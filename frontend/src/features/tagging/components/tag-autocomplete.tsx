"use client";

import { useState } from "react";

import { Input } from "@/shared/components/ui/input";
import { cn } from "@/shared/lib/utils";

import { useTags } from "../hooks/use-tags";

interface TagAutocompleteProps {
  /** "key" suggests distinct existing tag keys; "value" suggests distinct values. */
  field: "key" | "value";
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  /** Fired on Enter (used by the caller to commit the key=value pair). */
  onCommit?: () => void;
  autoFocus?: boolean;
  className?: string;
}

/**
 * Inline text input that suggests distinct existing tag keys/values as the
 * user types. Same "input + absolute dropdown list" shape as
 * `OrganismCombobox` — no generic combobox primitive exists in this codebase,
 * so this stays a small, single-purpose component rather than introducing one.
 */
export function TagAutocomplete({
  field,
  value,
  onChange,
  placeholder,
  onCommit,
  autoFocus,
  className,
}: TagAutocompleteProps) {
  const [open, setOpen] = useState(false);
  const { data: tags } = useTags({ q: value || undefined, limit: 25 });

  const suggestions = Array.from(
    new Set((tags ?? []).map((t) => (field === "key" ? t.key : (t.value ?? ""))).filter(Boolean)),
  )
    .filter((s) => s.toLowerCase() !== value.toLowerCase())
    .slice(0, 6);

  const showList = open && value.length > 0 && suggestions.length > 0;

  return (
    <div className="relative">
      <Input
        value={value}
        placeholder={placeholder}
        autoFocus={autoFocus}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            onCommit?.();
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
        className={cn("h-8 text-sm", className)}
      />
      {showList && (
        <ul className="absolute z-50 mt-1 max-h-48 w-full overflow-auto rounded-md border bg-popover py-1 text-sm text-popover-foreground shadow-md">
          {suggestions.map((s) => (
            <li key={s}>
              <button
                type="button"
                className="w-full px-3 py-1.5 text-left hover:bg-accent"
                onClick={() => {
                  onChange(s);
                  setOpen(false);
                }}
              >
                {s}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
