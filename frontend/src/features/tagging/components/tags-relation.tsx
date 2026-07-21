"use client";

import { Check, Plus } from "lucide-react";
import { useState } from "react";

import { TagChip } from "@/shared/components/tag-chip";
import { Button } from "@/shared/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";

import { useAssignTag, useEntityTags, useUnassignTag } from "../hooks/use-entity-tags";
import type { TaggableEntity } from "../types";
import { TagAutocomplete } from "./tag-autocomplete";

export interface TagsRelationProps {
  entity: TaggableEntity;
  id: string;
}

/**
 * Inline tag editor for a single entity: renders its assigned tags as
 * removable `TagChip`s, plus a "+ Tag" popover (two `TagAutocomplete` fields
 * + an Add button) to assign a new key[=value] pair.
 *
 * Mirrors chem-cellar's `TagsRelation` (screening-assay/components/run-relations.tsx),
 * adapted to prot-cellar's orval-generated tagging hooks, whose mutations take
 * `{ entityCollection, entityId, ... }` in the mutate-call variables rather
 * than binding them at hook-creation time.
 */
export function TagsRelation({ entity, id }: TagsRelationProps) {
  const { data: tags } = useEntityTags(entity, id);
  const assign = useAssignTag(entity, id);
  const unassign = useUnassignTag(entity, id);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");

  const list = tags ?? [];

  const add = () => {
    if (!key.trim()) return;
    assign.mutate(
      {
        entityCollection: entity,
        entityId: id,
        data: { key: key.trim(), value: value.trim() || null },
      },
      {
        // Keep the popover open for rapid multi-tagging; just clear the inputs.
        onSuccess: () => {
          setKey("");
          setValue("");
        },
      },
    );
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {list.length === 0 && (
        <span className="text-sm italic text-muted-foreground/70">No tags</span>
      )}
      {list.map((t) => (
        <TagChip
          key={t.id}
          tagKey={t.key}
          value={t.value}
          onRemove={() => unassign.mutate({ entityCollection: entity, entityId: id, tagId: t.id })}
        />
      ))}
      <Popover>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label="Add tag"
            className="h-6 gap-1 rounded-full border border-dashed px-2 text-xs text-muted-foreground hover:text-foreground"
          >
            <Plus className="h-3 w-3" /> Tag
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-80 space-y-2">
          <p className="text-xs font-medium">Add a tag</p>
          <div className="flex items-center gap-1.5">
            <div className="flex-1">
              <TagAutocomplete
                field="key"
                value={key}
                onChange={setKey}
                placeholder="key"
                onCommit={add}
                autoFocus
              />
            </div>
            <span className="text-muted-foreground">=</span>
            <div className="flex-1">
              <TagAutocomplete
                field="value"
                value={value}
                onChange={setValue}
                placeholder="value (optional)"
                onCommit={add}
              />
            </div>
            <Button
              type="button"
              size="sm"
              className="h-8 shrink-0"
              aria-label="Save tag"
              onClick={add}
              disabled={!key.trim() || assign.isPending}
            >
              <Check className="h-3.5 w-3.5" />
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
