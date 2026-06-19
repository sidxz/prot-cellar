"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import { Textarea } from "@/shared/components/ui/textarea";

import { useCreateOrganization, useUpdateOrganization } from "../hooks/use-organizations";
import { ORG_TYPE_LABELS, type Organization, type OrganizationType } from "../types";

// ── Schema ────────────────────────────────────────────────────────────────────

const ORG_TYPE_VALUES = Object.keys(ORG_TYPE_LABELS) as [OrganizationType, ...OrganizationType[]];

const formSchema = z.object({
  name: z.string().min(1, "Name is required"),
  org_type: z.enum(ORG_TYPE_VALUES),
  contact_name: z.string().optional(),
  // Optional, but must be a valid email when provided.
  contact_email: z
    .string()
    .trim()
    .email("Enter a valid email address")
    .optional()
    .or(z.literal("")),
  notes: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

// ── Defaults ──────────────────────────────────────────────────────────────────

const CREATE_DEFAULTS: FormValues = {
  name: "",
  org_type: "internal",
  contact_name: "",
  contact_email: "",
  notes: "",
};

function toFormValues(org: Organization): FormValues {
  return {
    name: org.name,
    org_type: org.org_type,
    contact_name: org.contact_name ?? "",
    contact_email: org.contact_email ?? "",
    notes: org.notes ?? "",
  };
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface OrganizationFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Pass an organization to switch to edit mode. */
  organization?: Organization;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function OrganizationFormDialog({
  open,
  onOpenChange,
  organization,
}: OrganizationFormDialogProps) {
  const isEdit = !!organization;
  const createMutation = useCreateOrganization();
  const updateMutation = useUpdateOrganization();
  const isPending = isEdit ? updateMutation.isPending : createMutation.isPending;

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: CREATE_DEFAULTS,
  });

  // Reset form whenever the dialog opens or organization changes
  useEffect(() => {
    if (open) {
      form.reset(organization ? toFormValues(organization) : CREATE_DEFAULTS);
    }
  }, [open, organization, form]);

  const onSubmit = async (values: FormValues) => {
    const contact_name = values.contact_name?.trim() || undefined;
    const contact_email = values.contact_email?.trim() || undefined;
    const notes = values.notes?.trim() || undefined;
    try {
      if (isEdit && organization) {
        await updateMutation.mutateAsync({
          orgId: organization.id,
          data: {
            name: values.name,
            org_type: values.org_type,
            contact_name,
            contact_email,
            notes,
          },
        });
      } else {
        await createMutation.mutateAsync({
          data: {
            name: values.name,
            org_type: values.org_type,
            contact_name,
            contact_email,
            notes,
          },
        });
      }
      onOpenChange(false);
    } catch {
      // Errors surface via the global mutation toast — do not add a second toast here.
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Organization" : "New Organization"}</DialogTitle>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)}>
          <div className="grid gap-5 py-4">
            {/* Name */}
            <div className="grid gap-2">
              <Label htmlFor="org_name">Name</Label>
              <Input id="org_name" placeholder="e.g. Acme Biopharma" {...form.register("name")} />
              {form.formState.errors.name && (
                <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>
              )}
            </div>

            {/* Org type — uses Controller for proper RHF integration (mirrors target-form-dialog) */}
            <div className="grid gap-2">
              <Label htmlFor="org_type">Type</Label>
              <Controller
                control={form.control}
                name="org_type"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="org_type" aria-label="Type">
                      <SelectValue placeholder="Select a type" />
                    </SelectTrigger>
                    <SelectContent>
                      {ORG_TYPE_VALUES.map((value) => (
                        <SelectItem key={value} value={value}>
                          {ORG_TYPE_LABELS[value]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {form.formState.errors.org_type && (
                <p className="text-xs text-destructive">{form.formState.errors.org_type.message}</p>
              )}
            </div>

            {/* Contact name */}
            <div className="grid gap-2">
              <Label htmlFor="contact_name">
                Contact name{" "}
                <span className="text-muted-foreground font-normal text-xs">(optional)</span>
              </Label>
              <Input
                id="contact_name"
                placeholder="e.g. Jane Doe"
                {...form.register("contact_name")}
              />
            </div>

            {/* Contact email */}
            <div className="grid gap-2">
              <Label htmlFor="contact_email">
                Contact email{" "}
                <span className="text-muted-foreground font-normal text-xs">(optional)</span>
              </Label>
              <Input
                id="contact_email"
                type="email"
                placeholder="e.g. jane@acme.com"
                {...form.register("contact_email")}
              />
              {form.formState.errors.contact_email && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.contact_email.message}
                </p>
              )}
            </div>

            {/* Notes */}
            <div className="grid gap-2">
              <Label htmlFor="notes">
                Notes <span className="text-muted-foreground font-normal text-xs">(optional)</span>
              </Label>
              <Textarea
                id="notes"
                rows={3}
                placeholder="Free-form notes…"
                {...form.register("notes")}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isPending || form.formState.isSubmitting}>
              {isPending
                ? isEdit
                  ? "Saving…"
                  : "Creating…"
                : isEdit
                  ? "Save Changes"
                  : "Create Organization"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
