"use client";

import { customInstance } from "@/shared/lib/api/custom-instance";
import { showSuccess } from "@/shared/lib/toast";
import {
  type QueryClient,
  type UseQueryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

/**
 * Normalize a list endpoint response to a bare array.
 *
 * Endpoints using cursor pagination return a `{ items }` envelope;
 * older ones return a bare list. Accepts both shapes so list hooks
 * don't need to know which shape they receive.
 */
export function unwrapList<T>(data: T[] | { items: T[] } | undefined): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.items;
}

export interface CrudHooksConfig {
  entityName: string;
  baseUrl: string;
  queryKey: string[];
  parentQueryKeys?: string[][];
  /** Override per-action toast messages. */
  messages?: {
    created?: (entityName: string) => string;
    updated?: (entityName: string) => string;
    deleted?: (entityName: string) => string;
    actionDefault?: (entityName: string, action: string) => string;
  };
}

export function createCrudHooks<
  TEntity,
  TCreateInput = Record<string, unknown>,
  TUpdateInput = Record<string, unknown>,
>(config: CrudHooksConfig) {
  const { entityName, baseUrl, queryKey, parentQueryKeys = [], messages } = config;
  const createdMsg = messages?.created ?? ((n) => `${n} created`);
  const updatedMsg = messages?.updated ?? ((n) => `${n} updated`);
  const deletedMsg = messages?.deleted ?? ((n) => `${n} deleted`);
  const actionDefaultMsg = messages?.actionDefault ?? ((n, a) => `${n} ${a} complete`);

  function invalidateAll(qc: QueryClient) {
    qc.invalidateQueries({ queryKey });
    for (const key of parentQueryKeys) {
      qc.invalidateQueries({ queryKey: key });
    }
  }

  function useList(
    params?: Record<string, string>,
    options?: Partial<UseQueryOptions<TEntity[]>>,
  ) {
    return useQuery({
      queryKey: params ? [...queryKey, params] : queryKey,
      queryFn: async () => {
        const resp = await customInstance<TEntity[] | { items: TEntity[] }>({
          url: baseUrl,
          method: "GET",
          params,
        });
        return unwrapList(resp);
      },
      ...options,
    });
  }

  function useGet(id: string | undefined, options?: Partial<UseQueryOptions<TEntity>>) {
    return useQuery({
      queryKey: [...queryKey, id],
      queryFn: () => customInstance<TEntity>({ url: `${baseUrl}/${id}`, method: "GET" }),
      enabled: !!id,
      ...options,
    });
  }

  function useCreate() {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: (data: TCreateInput) =>
        customInstance<TEntity>({ url: baseUrl, method: "POST", data }),
      onSuccess: () => {
        invalidateAll(qc);
        showSuccess(createdMsg(entityName));
      },
    });
  }

  function useUpdate(id: string) {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: (data: TUpdateInput) =>
        customInstance<TEntity>({
          url: `${baseUrl}/${id}`,
          method: "PATCH",
          data,
        }),
      onSuccess: () => {
        invalidateAll(qc);
        showSuccess(updatedMsg(entityName));
      },
    });
  }

  function useDelete() {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: (id: string) =>
        customInstance<void>({ url: `${baseUrl}/${id}`, method: "DELETE" }),
      onSuccess: () => {
        invalidateAll(qc);
        showSuccess(deletedMsg(entityName));
      },
    });
  }

  function useAction(action: string, successMessage?: string) {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: ({ id, data }: { id: string; data?: unknown }) =>
        customInstance<TEntity>({
          url: `${baseUrl}/${id}/${action}`,
          method: "POST",
          data,
        }),
      onSuccess: () => {
        invalidateAll(qc);
        showSuccess(successMessage ?? actionDefaultMsg(entityName, action));
      },
    });
  }

  return { useList, useGet, useCreate, useUpdate, useDelete, useAction };
}
