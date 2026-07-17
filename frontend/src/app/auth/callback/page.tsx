"use client";

import { Button } from "@/shared/components/ui/button";
import { LogoMark } from "@/shared/components/ui/logo-mark";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { AuthzCallback } from "@sentinel-auth/nextjs";
import { useRouter } from "next/navigation";

export default function CallbackPage() {
  const router = useRouter();

  return (
    <div className="fixed inset-0 overflow-hidden bg-background">
      {/* ── Left: CSS gradient background (mirrors login) ── */}
      <div className="absolute inset-0 md:right-[460px]" aria-hidden="true">
        <div
          className="h-full w-full"
          style={{
            background:
              "radial-gradient(ellipse 80% 60% at 20% 40%, oklch(0.45 0.14 185 / 0.35) 0%, transparent 60%), " +
              "radial-gradient(ellipse 60% 80% at 80% 70%, oklch(0.5 0.12 260 / 0.25) 0%, transparent 55%), " +
              "radial-gradient(ellipse 70% 50% at 50% 10%, oklch(0.55 0.10 150 / 0.18) 0%, transparent 50%), " +
              "oklch(0.16 0.015 255)",
          }}
        >
          <div
            className="absolute inset-0"
            style={{
              backgroundImage:
                "radial-gradient(circle, oklch(0.9 0 0 / 0.06) 1px, transparent 1px)",
              backgroundSize: "28px 28px",
            }}
          />
        </div>
      </div>

      {/* ── Right: branding + callback ── */}
      <div className="relative z-20 flex min-h-screen flex-col md:ml-auto md:w-[460px] md:border-l md:border-sidebar-border md:bg-sidebar">
        {/* Top-right branding */}
        <div
          className="flex flex-col items-end px-8 pt-8"
          style={{ animation: "auth-enter 0.7s ease-out 0.1s both" }}
        >
          <div className="flex items-center gap-3">
            <LogoMark className="size-12" />
            <h1
              className="text-3xl font-medium tracking-tight"
              style={{ fontFamily: "var(--font-overused-grotesk), ui-sans-serif, sans-serif" }}
            >
              ProtCellar
            </h1>
          </div>
          <span className="text-xs text-muted-foreground">protein &amp; target platform</span>
        </div>

        {/* Centered callback content */}
        <div className="flex flex-1 flex-col items-center justify-center">
          <div className="w-full max-w-[320px] px-6 md:px-0">
            <div style={{ animation: "auth-enter 0.7s ease-out 0.2s both" }}>
              <AuthzCallback
                // `returnTo` is the path the user was on before a silent re-auth
                // redirect — restore their place instead of always landing on "/".
                onSuccess={(_user, returnTo) => router.replace(returnTo ?? "/")}
                onError={(error) =>
                  router.replace(`/login?error=${encodeURIComponent(error.message)}`)
                }
                // Silent (prompt=none) re-auth needs user interaction — the stale
                // session is already cleared, so fall back to interactive login.
                onSilentReauthFailed={() => router.replace("/login")}
                loadingComponent={
                  <div>
                    <h2 className="text-sm font-medium text-muted-foreground">Signing in...</h2>
                    <div className="mt-4 space-y-3">
                      <Skeleton className="h-4 w-full" />
                      <Skeleton className="h-4 w-3/4" />
                    </div>
                  </div>
                }
                workspaceSelector={({ workspaces, onSelect, isLoading: selecting }) => (
                  <div>
                    <h2 className="text-sm font-medium text-muted-foreground">
                      Select workspace to continue
                    </h2>
                    <div className="mt-4 space-y-2">
                      {workspaces.map((ws) => (
                        <Button
                          key={ws.id}
                          variant="outline"
                          className="w-full justify-start rounded-[11px]"
                          disabled={selecting}
                          onClick={() => onSelect(ws.id)}
                        >
                          <span className="truncate">{ws.name}</span>
                          <span className="ml-auto text-xs text-muted-foreground">{ws.role}</span>
                        </Button>
                      ))}
                    </div>
                  </div>
                )}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
