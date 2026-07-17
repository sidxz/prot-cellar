import { useQueryClient } from "@tanstack/react-query";

import { useGetImportRunApiV1ImportsImportRunIdGet } from "@/shared/lib/api/imports/imports";
import { ImportStatus } from "@/shared/lib/api/model";
import {
  getListPluginsApiV1PluginsGetQueryKey,
  useListPluginsApiV1PluginsGet,
  useSetPluginEnabledApiV1PluginsPluginIdEnabledPut,
  useStartPluginRunApiV1PluginsPluginIdRunsPost,
} from "@/shared/lib/api/plugins/plugins";
import { showSuccess } from "@/shared/lib/toast";

/** Statuses still in progress — poll while in one of these. */
const ACTIVE_STATUSES: ImportStatus[] = [ImportStatus.queued, ImportStatus.running];

/** Catalog of registered plugins (manifests). */
export function usePluginCatalog() {
  return useListPluginsApiV1PluginsGet();
}

/** Start a plugin run (dry-run preview or real). Toasts on success. */
export function useStartPluginRun() {
  return useStartPluginRunApiV1PluginsPluginIdRunsPost({
    mutation: { onSuccess: () => showSuccess("Plugin run started") },
  });
}

/** Enable/disable a plugin for the current workspace; refreshes the catalog. */
export function useSetPluginEnabled() {
  const qc = useQueryClient();
  return useSetPluginEnabledApiV1PluginsPluginIdEnabledPut({
    mutation: {
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: getListPluginsApiV1PluginsGetQueryKey() });
      },
    },
  });
}

/** Poll a (preview) run every 2s while active; disabled when runId is null. */
export function usePluginPreview(runId: string | null) {
  return useGetImportRunApiV1ImportsImportRunIdGet(runId ?? "", {
    query: {
      enabled: Boolean(runId),
      refetchInterval: (query) => {
        const status = query.state.data?.status;
        return status && ACTIVE_STATUSES.includes(status) ? 2000 : false;
      },
    },
  });
}
