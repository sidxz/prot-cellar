"use client";

import { Building2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { DataGrid } from "@/shared/components/data-grid/data-grid";
import { Button } from "@/shared/components/ui/button";

import { useOrganizations } from "../hooks/use-organizations";
import { organizationColumnDefs } from "./organization-columns";
import { OrganizationFormDialog } from "./organization-form-dialog";

function OrganizationsEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-center text-muted-foreground">
      <Building2 className="h-10 w-10 opacity-30" />
      <p className="text-sm font-medium">No organizations found</p>
      <p className="text-xs">
        Create your first organization using the "New Organization" button above.
      </p>
    </div>
  );
}

export function OrganizationListPage() {
  const router = useRouter();
  const [includeInactive, setIncludeInactive] = useState(false);
  const [cursorStack, setCursorStack] = useState<(string | undefined)[]>([undefined]);
  const currentCursor = cursorStack[cursorStack.length - 1];

  const { data, isLoading, isError } = useOrganizations(currentCursor, includeInactive);

  const organizations = useMemo(() => {
    if (!data?.items) return undefined;
    // biome-ignore lint/suspicious/noExplicitAny: narrowing cast at feature boundary
    return data.items as any[];
  }, [data]);

  const [newOpen, setNewOpen] = useState(false);

  function goNext() {
    const nextCursor = data?.next_cursor;
    if (!nextCursor) return;
    setCursorStack((prev) => [...prev, String(nextCursor)]);
  }
  function goPrev() {
    if (cursorStack.length <= 1) return;
    setCursorStack((prev) => prev.slice(0, -1));
  }
  function toggleInactive(next: boolean) {
    setIncludeInactive(next);
    setCursorStack([undefined]); // reset pagination when the filter changes
  }

  const hasNext = !!data?.next_cursor;
  const hasPrev = cursorStack.length > 1;

  if (isError) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Organizations</h1>
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to load organizations. Check that the backend is running.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Organizations</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Manage workspace organizations</p>
        </div>
        <div className="flex items-center gap-3">
          {/* No Switch/Checkbox primitive in the repo — a Button toggle keeps us dependency-free. */}
          <Button
            type="button"
            variant={includeInactive ? "secondary" : "outline"}
            size="sm"
            aria-pressed={includeInactive}
            onClick={() => toggleInactive(!includeInactive)}
          >
            {includeInactive ? "Showing inactive" : "Show inactive"}
          </Button>
          <Button type="button" size="sm" onClick={() => setNewOpen(true)}>
            New Organization
          </Button>
        </div>
      </div>

      <DataGrid
        rowData={organizations}
        columnDefs={organizationColumnDefs}
        loading={isLoading}
        height="calc(100vh - 240px)"
        suppressFilters
        searchPlaceholder={false}
        onRowClick={(org) => router.push(`/admin/organizations/${org.id}`)}
        emptyState={<OrganizationsEmptyState />}
      />

      {(hasPrev || hasNext) && (
        <div className="flex items-center justify-end gap-2">
          <Button type="button" variant="outline" size="sm" onClick={goPrev} disabled={!hasPrev}>
            Previous
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={goNext} disabled={!hasNext}>
            Next
          </Button>
        </div>
      )}

      <OrganizationFormDialog open={newOpen} onOpenChange={setNewOpen} />
    </div>
  );
}
