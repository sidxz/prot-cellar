// frontend/src/features/import-hub/components/start-import-dialog.tsx
"use client";

import { useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Label } from "@/shared/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import { ImportType } from "@/shared/lib/api/model";

import { IMPORT_TYPE_LABELS } from "../types";
import { GeneEnrichmentForm } from "./param-forms/gene-enrichment-form";
import { GoOntologyForm } from "./param-forms/go-ontology-form";
import { ProteomeForm } from "./param-forms/proteome-form";

const IMPORT_TYPE_VALUES = Object.values(ImportType);

interface StartImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function StartImportDialog({ open, onOpenChange }: StartImportDialogProps) {
  const [importType, setImportType] = useState<ImportType>(ImportType.go_ontology);
  const close = () => onOpenChange(false);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New import</DialogTitle>
          <DialogDescription>Choose an import type and provide its parameters.</DialogDescription>
        </DialogHeader>

        <div className="grid gap-2">
          <Label htmlFor="import_type">Import type</Label>
          <Select value={importType} onValueChange={(v) => setImportType(v as ImportType)}>
            <SelectTrigger id="import_type" aria-label="Import type">
              <SelectValue placeholder="Select a type" />
            </SelectTrigger>
            <SelectContent>
              {IMPORT_TYPE_VALUES.map((t) => (
                <SelectItem key={t} value={t}>
                  {IMPORT_TYPE_LABELS[t]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {importType === ImportType.go_ontology && <GoOntologyForm key="go" onSuccess={close} />}
        {importType === ImportType.proteome && <ProteomeForm key="prot" onSuccess={close} />}
        {importType === ImportType.gene_enrichment && (
          <GeneEnrichmentForm key="gene" onSuccess={close} />
        )}
      </DialogContent>
    </Dialog>
  );
}
