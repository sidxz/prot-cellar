import { describe, expect, it } from "vitest";
import { shouldAutoReauth } from "./auto-reauth";

describe("shouldAutoReauth", () => {
  it("enables auto re-auth on protected app routes", () => {
    expect(shouldAutoReauth("/")).toBe(true);
    expect(shouldAutoReauth("/proteins")).toBe(true);
    expect(shouldAutoReauth("/organisms/123")).toBe(true);
  });

  it("disables auto re-auth on the login route (would hijack interactive sign-in)", () => {
    expect(shouldAutoReauth("/login")).toBe(false);
    expect(shouldAutoReauth("/login/")).toBe(false);
  });

  it("disables auto re-auth on the callback route (would preempt the OAuth response)", () => {
    expect(shouldAutoReauth("/auth")).toBe(false);
    expect(shouldAutoReauth("/auth/callback")).toBe(false);
  });

  it("is a safe no-op when the pathname is unknown", () => {
    expect(shouldAutoReauth(null)).toBe(false);
  });
});
