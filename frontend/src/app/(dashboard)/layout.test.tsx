import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

const useAuthzMock = vi.fn();
vi.mock("@duar-auth/nextjs", () => ({ useAuthz: () => useAuthzMock() }));

// Stub the heavy chrome so the test only exercises the auth gate.
vi.mock("@/shared/components/layout/app-sidebar", () => ({
  AppSidebar: () => <div data-testid="app-sidebar" />,
}));
vi.mock("@/shared/components/layout/header", () => ({
  Header: () => <div data-testid="header" />,
}));
vi.mock("@/shared/components/ui/sidebar", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: test stub
  SidebarProvider: ({ children }: any) => <div>{children}</div>,
  // biome-ignore lint/suspicious/noExplicitAny: test stub
  SidebarInset: ({ children }: any) => <div>{children}</div>,
}));

import DashboardLayout from "./layout";

describe("DashboardLayout auth gate", () => {
  beforeEach(() => {
    replace.mockClear();
    useAuthzMock.mockReset();
  });

  it("redirects to /login when the session is unauthenticated", () => {
    useAuthzMock.mockReturnValue({
      authState: "unauthenticated",
      isAuthenticated: false,
      isLoading: false,
    });

    render(
      <DashboardLayout>
        <div data-testid="child" />
      </DashboardLayout>,
    );

    expect(replace).toHaveBeenCalledWith("/login");
    expect(screen.queryByTestId("child")).toBeNull();
  });

  it("does NOT redirect during needs_reauth so silent re-auth can run", () => {
    useAuthzMock.mockReturnValue({
      authState: "needs_reauth",
      isAuthenticated: false,
      isLoading: false,
    });

    render(
      <DashboardLayout>
        <div data-testid="child" />
      </DashboardLayout>,
    );

    expect(replace).not.toHaveBeenCalled();
    // Still gated (shows skeleton), but no bounce to /login.
    expect(screen.queryByTestId("child")).toBeNull();
  });

  it("renders children when authenticated", () => {
    useAuthzMock.mockReturnValue({
      authState: "authenticated",
      isAuthenticated: true,
      isLoading: false,
    });

    render(
      <DashboardLayout>
        <div data-testid="child" />
      </DashboardLayout>,
    );

    expect(replace).not.toHaveBeenCalled();
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });

  it("shows skeleton without redirecting while auth is still loading", () => {
    useAuthzMock.mockReturnValue({
      authState: "unauthenticated",
      isAuthenticated: false,
      isLoading: true,
    });

    render(
      <DashboardLayout>
        <div data-testid="child" />
      </DashboardLayout>,
    );

    expect(replace).not.toHaveBeenCalled();
    expect(screen.queryByTestId("child")).toBeNull();
  });
});
