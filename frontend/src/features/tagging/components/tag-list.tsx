"use client";

import { GitMerge, Pencil, Tag as TagIcon, Trash2 } from "lucide-react";
import { useState } from "react";

import { TagChip } from "@/shared/components/tag-chip";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { useAuthzHasRole } from "@duar-auth/nextjs";

import { useDeleteTag, useTags } from "../hooks/use-tags";
import type { Tag } from "../types";
import { TagMergeDialog } from "./tag-merge-dialog";
import { TagRenameDialog } from "./tag-rename-dialog";

const TH = "px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground";
const TD = "px-3 py-2 align-middle";

/**
 * Admin tag management: search + a table of every workspace tag with
 * Rename / Merge / Delete actions. Backend enforces admin on those mutating
 * routes (403 otherwise), so actions are only rendered for admins here too —
 * same gate chem-cellar uses, via `useAuthzHasRole("admin")`.
 */
export function TagList() {
  const [q, setQ] = useState("");
  const { data: tags, isLoading } = useTags({ q: q || undefined, limit: 200 });
  const del = useDeleteTag();
  const isAdmin = useAuthzHasRole("admin");
  const [renaming, setRenaming] = useState<Tag | null>(null);
  const [merging, setMerging] = useState<Tag | null>(null);

  function handleDelete(tag: Tag) {
    const label = tag.value ? `${tag.key}=${tag.value}` : tag.key;
    if (!window.confirm(`Delete tag "${label}"? This removes it from every entity.`)) return;
    del.mutate({ tagId: tag.id });
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Tags</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Rename, merge, or remove workspace tags.
          </p>
        </div>
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search tags…"
          className="h-9 w-56"
        />
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading tags…</p>
      ) : tags && tags.length > 0 ? (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-muted/40">
                <th className={TH}>Tag</th>
                <th className={TH}>Created</th>
                {isAdmin && <th className={`${TH} w-[220px]`} />}
              </tr>
            </thead>
            <tbody>
              {tags.map((t) => (
                <tr key={t.id} className="border-t border-border">
                  <td className={TD}>
                    <TagChip tagKey={t.key} value={t.value} />
                  </td>
                  <td className={`${TD} text-xs text-muted-foreground`}>
                    {new Date(t.created_at).toLocaleDateString()}
                  </td>
                  {isAdmin && (
                    <td className={TD}>
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => setRenaming(t)}>
                          <Pencil className="mr-1 h-3.5 w-3.5" /> Rename
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setMerging(t)}>
                          <GitMerge className="mr-1 h-3.5 w-3.5" /> Merge
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(t)}
                          disabled={del.isPending}
                        >
                          <Trash2 className="h-3.5 w-3.5 text-destructive" />
                          <span className="sr-only">Delete</span>
                        </Button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center gap-2 py-20 text-center text-muted-foreground">
          <TagIcon className="h-10 w-10 opacity-30" />
          <p className="text-sm font-medium">No tags yet.</p>
        </div>
      )}

      <TagRenameDialog
        tag={renaming}
        open={!!renaming}
        onOpenChange={(o) => !o && setRenaming(null)}
      />
      <TagMergeDialog tag={merging} open={!!merging} onOpenChange={(o) => !o && setMerging(null)} />
    </div>
  );
}
