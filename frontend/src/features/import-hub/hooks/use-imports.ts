import { useQueryClient } from "@tanstack/react-query";

import {
  getListImportRunsApiV1ImportsGetQueryKey,
  useGetImportRunApiV1ImportsImportRunIdGet,
  useListImportRunsApiV1ImportsGet,
  useStartImportApiV1ImportsPost,
  useUploadEssentialityFileApiV1ImportsUploadsPost,
} from "@/shared/lib/api/imports/imports";
import type { BodyUploadEssentialityFileApiV1ImportsUploadsPost } from "@/shared/lib/api/model";
import { ImportStatus, type ImportType } from "@/shared/lib/api/model";
import { showSuccess } from "@/shared/lib/toast";

/** Statuses still in progress — poll while in one of these. */
const ACTIVE_STATUSES: ImportStatus[] = [ImportStatus.queued, ImportStatus.running];

/** List import runs (cursor pagination). No auto-poll — the list has a manual refresh. */
export function useImportList(cursor?: string) {
  return useListImportRunsApiV1ImportsGet({ cursor: cursor ?? undefined });
}

/** Fetch one run; polls every 2s while queued/running, stops on a terminal status. */
export function useImportRun(id: string) {
  return useGetImportRunApiV1ImportsImportRunIdGet(id, {
    query: {
      refetchInterval: (query) => {
        const status = query.state.data?.status;
        return status && ACTIVE_STATUSES.includes(status) ? 2000 : false;
      },
    },
  });
}

/** Start an import; invalidates the list and toasts on success. */
export function useStartImport() {
  const queryClient = useQueryClient();
  return useStartImportApiV1ImportsPost({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getListImportRunsApiV1ImportsGetQueryKey(),
        });
        showSuccess("Import started");
      },
    },
  });
}

/**
 * Upload a file → resolves to { upload_ref }. Omitting `importType` keeps the
 * route's default behaviour (convert to the DeJesus locus/call TSV); passing
 * `ImportType.target_biology` stores the workbook's raw bytes instead (see
 * the route's own docstring in imports.ts) — required for `parse_workbook`,
 * which needs a real multi-sheet XLSX.
 */
export function useUploadEssentiality(importType?: ImportType) {
  const mutation = useUploadEssentialityFileApiV1ImportsUploadsPost({
    mutation: { onSuccess: () => showSuccess("File uploaded") },
  });
  return {
    ...mutation,
    mutateAsync: (vars: { data: BodyUploadEssentialityFileApiV1ImportsUploadsPost }) =>
      mutation.mutateAsync({
        ...vars,
        params: importType ? { import_type: importType } : undefined,
      }),
  };
}
