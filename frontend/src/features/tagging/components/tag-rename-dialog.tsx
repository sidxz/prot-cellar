"use client";

import { useEffect, useState } from "react";

import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";

import { useRenameTag } from "../hooks/use-tags";
import type { Tag } from "../types";

interface TagRenameDialogProps {
  tag: Tag | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Edits a tag's key/value. Ported from chem-cellar; adapted to this repo's
 * `useRenameTag()` (no bound id — id goes in the mutate payload). */
export function TagRenameDialog({ tag, open, onOpenChange }: TagRenameDialogProps) {
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const rename = useRenameTag();

  // biome-ignore lint/correctness/useExhaustiveDependencies: `open` intentionally resets the form when the dialog reopens
  useEffect(() => {
    if (tag) {
      setKey(tag.key);
      setValue(tag.value ?? "");
    }
  }, [tag, open]);

  const submit = () => {
    if (!tag) return;
    rename.mutate(
      { tagId: tag.id, data: { key: key.trim(), value: value.trim() || null } },
      { onSuccess: () => onOpenChange(false) },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Rename tag</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="tag-key">Key</Label>
            <Input id="tag-key" value={key} onChange={(e) => setKey(e.target.value)} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="tag-value">Value (optional)</Label>
            <Input id="tag-value" value={value} onChange={(e) => setValue(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!key.trim() || rename.isPending}>
            {rename.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
