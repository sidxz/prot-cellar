import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/shared/lib/auth/config", () => ({
  getAuthHeaders: () => ({ Authorization: "Bearer test-token" }),
}));

import { ApiError, API_V1, customInstance, setApiBaseUrl } from "./custom-instance";

const fetchMock = vi.fn();
beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  setApiBaseUrl("http://localhost:8001");
  fetchMock.mockReset();
});
afterEach(() => vi.unstubAllGlobals());

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("customInstance", () => {
  it("prefixes the base URL and attaches auth header", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "1" }));
    const out = await customInstance<{ id: string }>({ url: "/api/v1/proteins/P1", method: "GET" });
    expect(out).toEqual({ id: "1" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8001/api/v1/proteins/P1");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("serializes array params as repeated keys (FastAPI list[T])", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await customInstance({ url: "/api/v1/proteins", method: "GET", params: { id: ["a", "b"], q: "x" } });
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("id=a&id=b");
    expect(url).toContain("q=x");
  });

  it("returns undefined for 204", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    const out = await customInstance<undefined>({ url: "/api/v1/x", method: "DELETE" });
    expect(out).toBeUndefined();
  });

  it("throws ApiError carrying status + detail on non-2xx", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "nope" }, 409));
    await expect(customInstance({ url: "/api/v1/x", method: "POST" })).rejects.toMatchObject({
      status: 409,
      detail: "nope",
    });
    await expect(customInstance({ url: "/api/v1/x", method: "POST" })).rejects.toBeInstanceOf(ApiError);
  });

  it("exposes API_V1 constant", () => {
    expect(API_V1).toBe("/api/v1");
  });
});
