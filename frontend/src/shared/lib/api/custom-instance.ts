// Custom fetch instance for orval-generated API client.
// Base URL set at runtime via setApiBaseUrl() from AppConfig.
// Auth tokens injected via getAuthHeaders() from the shared auth config (Task 9).

import { getAuthHeaders } from "@/shared/lib/auth/config";

let _baseUrl = "";

/**
 * Versioned API path prefix shared by every hand-written hook/component that
 * builds a request URL by hand. Compose URLs as `${API_V1}/...` instead of
 * hard-coding the `/api/v1` literal at each call site.
 */
export const API_V1 = "/api/v1";

/** Called by AuthProvider after fetching runtime AppConfig. */
export function setApiBaseUrl(url: string): void {
  _baseUrl = url.replace(/\/$/, "");
}

/**
 * Error thrown by {@link customInstance} for any non-2xx response.
 *
 * Extends the native `Error` so existing callers that only read `.message`
 * (or check `instanceof Error`) keep working unchanged. Callers that need to
 * branch on the server's structured payload can narrow via `instanceof ApiError`
 * and inspect `status` + `detail`.
 */
export class ApiError extends Error {
  /** HTTP status code of the failed response. */
  readonly status: number;
  /**
   * Parsed `detail` field from the JSON response body, or the full parsed body
   * when no `detail` key is present, or `undefined` when the body was empty /
   * not JSON. FastAPI emits `{detail: "..."}` or `{detail: [{loc, msg}]}`.
   */
  readonly detail: unknown;

  constructor(public readonly statusCode: number, message: string, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = statusCode;
    this.detail = detail;
  }
}

/**
 * Core fetch wrapper used by orval-generated clients and hand-written hooks.
 *
 * - Prepends `_baseUrl` to the path.
 * - Serializes array params as repeated keys (`k=a&k=b`) for FastAPI `list[T]`.
 * - Merges `getAuthHeaders()` into request headers.
 * - Sets `Content-Type: application/json` unless body is `FormData`.
 * - 204 responses → `undefined`.
 * - Non-2xx → throws `ApiError` with `status` and parsed `detail`.
 */
export const customInstance = async <T>({
  url,
  method,
  params,
  data,
  headers,
  signal,
}: {
  url: string;
  method: string;
  // biome-ignore lint/suspicious/noExplicitAny: orval generates params with mixed primitive types
  params?: Record<string, any>;
  data?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}): Promise<T> => {
  // Build query string. Arrays are emitted as repeated keys (`k=a&k=b`),
  // matching FastAPI's `list[T] = Query(...)` expectation. Scalars are
  // stringified; null/undefined entries (and null/undefined array items)
  // are skipped.
  const searchParams = new URLSearchParams();
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v == null) continue;
      if (Array.isArray(v)) {
        for (const item of v) {
          if (item == null) continue;
          searchParams.append(k, String(item));
        }
      } else {
        searchParams.append(k, String(v));
      }
    }
  }
  const queryString = searchParams.toString() ? `?${searchParams.toString()}` : "";

  const authHeaders = getAuthHeaders();
  const isFormData = typeof FormData !== "undefined" && data instanceof FormData;

  const fetchHeaders: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...authHeaders,
    ...headers,
  };

  const response = await fetch(`${_baseUrl}${url}${queryString}`, {
    method,
    headers: fetchHeaders,
    signal,
    ...(data
      ? { body: isFormData ? (data as FormData) : JSON.stringify(data) }
      : {}),
  });

  if (!response.ok) {
    // Surface the response body's `detail` so callers see what the server
    // actually rejected. FastAPI emits two shapes:
    //   - custom errors: `{detail: "string message"}`
    //   - Pydantic validation: `{detail: [{loc, msg, type}]}`
    let parsedBody: unknown;
    let detail: unknown;
    try {
      parsedBody = await response.json();
      const parsed = parsedBody as { detail?: unknown } | null;
      if (parsed != null && "detail" in parsed) {
        detail = parsed.detail;
      } else {
        detail = parsedBody;
      }
    } catch {
      // body not JSON or already consumed — fall through with no detail
    }
    throw new ApiError(
      response.status,
      detail != null
        ? `API error: ${response.status} — ${typeof detail === "string" ? detail : JSON.stringify(detail)}`
        : `API error: ${response.status}`,
      detail,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
};
