"use client";

import { ProteinFold } from "@/shared/components/backgrounds/protein-fold";
import { LogoMark } from "@/shared/components/ui/logo-mark";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { forgetWorkspace } from "@/shared/lib/auth/workspace-memory";
import { AuthzCallback } from "@duar-auth/nextjs";
import { useRouter } from "next/navigation";
import { WorkspaceSelector } from "./workspace-selector";

export default function CallbackPage() {
  const router = useRouter();

  return (
    <div className="fixed inset-0 overflow-hidden bg-background">
      {/* ── Left: rotating protein-fold cover (mirrors login) ── */}
      <div className="absolute inset-0 md:right-[460px]" aria-hidden="true">
        <ProteinFold />
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
                onError={(error) => {
                  // A failed auto-entry must not loop — forget the remembered
                  // workspace so the next sign-in shows the picker again.
                  forgetWorkspace();
                  router.replace(`/login?error=${encodeURIComponent(error.message)}`);
                }}
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
                workspaceSelector={(props) => <WorkspaceSelector {...props} />}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
