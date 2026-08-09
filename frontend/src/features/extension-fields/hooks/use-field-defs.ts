import { useQueryClient } from "@tanstack/react-query";

import {
  getListFieldDefsApiV1ExtensionFieldsGetQueryKey,
  useCreateFieldDefApiV1ExtensionFieldsPost,
  useDeleteFieldDefApiV1ExtensionFieldsFieldDefIdDelete,
  useListFieldDefsApiV1ExtensionFieldsGet,
  useUpdateFieldDefApiV1ExtensionFieldsFieldDefIdPatch,
} from "@/shared/lib/api/extension-fields/extension-fields";
import type { RecordKind } from "@/shared/lib/api/model";
import { showSuccess } from "@/shared/lib/toast";

/** List extension field declarations, optionally scoped to one record kind.
 *  Omit `kind` to fetch the whole workspace registry (the kind-list screen's
 *  per-kind counts come from one unfiltered call rather than eight). */
export function useFieldDefs(kind?: RecordKind) {
  return useListFieldDefsApiV1ExtensionFieldsGet(kind ? { kind } : undefined);
}

/**
 * Declare a new extension field.
 * On success: invalidates every field-defs list (all-kinds and per-kind alike
 * share the same key prefix) and shows a success toast.
 * No onError — the global MutationCache handles the error toast.
 */
export function useCreateFieldDef() {
  const queryClient = useQueryClient();
  return useCreateFieldDefApiV1ExtensionFieldsPost({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getListFieldDefsApiV1ExtensionFieldsGetQueryKey(),
        });
        showSuccess("Field added");
      },
    },
  });
}

/**
 * Update an existing extension field's label, shape, position, or table visibility.
 * On success: invalidates every field-defs list and shows a success toast.
 * No onError — the global MutationCache handles the error toast.
 */
export function useUpdateFieldDef() {
  const queryClient = useQueryClient();
  return useUpdateFieldDefApiV1ExtensionFieldsFieldDefIdPatch({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getListFieldDefsApiV1ExtensionFieldsGetQueryKey(),
        });
        showSuccess("Field updated");
      },
    },
  });
}

/**
 * Delete a field declaration. Values already stored under its name in any
 * record's `extensions` bag are kept — they are not touched, only orphaned.
 * On success: invalidates every field-defs list and shows a success toast.
 * No onError — the global MutationCache handles the error toast.
 */
export function useDeleteFieldDef() {
  const queryClient = useQueryClient();
  return useDeleteFieldDefApiV1ExtensionFieldsFieldDefIdDelete({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getListFieldDefsApiV1ExtensionFieldsGetQueryKey(),
        });
        showSuccess("Field deleted");
      },
    },
  });
}
