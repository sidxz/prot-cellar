"use client";

import { useAppConfig } from "@/shared/lib/app-config";
import { useAuthz } from "@sentinel-auth/nextjs";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

function GoogleIcon() {
  return (
    <svg className="h-[18px] w-[18px]" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  );
}

function EntraIcon() {
  return (
    <svg className="h-[18px] w-[18px]" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M11.5 2L2 7.5v9L11.5 22 21 16.5v-9L11.5 2z"
        fill="none"
        stroke="#0078D4"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M11.5 2v20M2 7.5l9.5 5 9.5-5" stroke="#0078D4" strokeWidth="1.5" fill="none" />
    </svg>
  );
}

export default function LoginPage() {
  const { isAuthenticated, isLoading, login } = useAuthz();
  const { idp } = useAppConfig();
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated) {
      router.replace("/");
    }
  }, [isAuthenticated, router]);

  if (isLoading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-sidebar">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  const hasGoogle = Boolean(idp.googleClientId);
  const hasEntra = Boolean(idp.entraClientId);
  // Fall back to "google" when config not yet loaded
  const showGoogle = hasGoogle || (!hasGoogle && !hasEntra);

  return (
    <div className="fixed inset-0 overflow-hidden bg-background">
      {/* ── Left: CSS gradient/grid background ── */}
      <div className="absolute inset-0 md:right-[460px]" aria-hidden="true">
        {/* Bio-themed CSS gradient background — no gsap/GridMotion */}
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
          {/* Subtle dot-grid overlay */}
          <div
            className="absolute inset-0"
            style={{
              backgroundImage:
                "radial-gradient(circle, oklch(0.9 0 0 / 0.06) 1px, transparent 1px)",
              backgroundSize: "28px 28px",
            }}
          />
          {/* Decorative helix-like arcs via pure CSS */}
          <svg
            role="presentation"
            className="absolute inset-0 h-full w-full"
            xmlns="http://www.w3.org/2000/svg"
            preserveAspectRatio="xMidYMid slice"
          >
            <defs>
              <linearGradient id="arc1" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="oklch(0.55 0.11 185)" stopOpacity="0.12" />
                <stop offset="100%" stopColor="oklch(0.55 0.11 185)" stopOpacity="0" />
              </linearGradient>
              <linearGradient id="arc2" x1="100%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="oklch(0.55 0.12 260)" stopOpacity="0.10" />
                <stop offset="100%" stopColor="oklch(0.55 0.12 260)" stopOpacity="0" />
              </linearGradient>
            </defs>
            <ellipse
              cx="30%"
              cy="50%"
              rx="35%"
              ry="55%"
              fill="none"
              stroke="url(#arc1)"
              strokeWidth="1"
            />
            <ellipse
              cx="70%"
              cy="45%"
              rx="28%"
              ry="45%"
              fill="none"
              stroke="url(#arc2)"
              strokeWidth="1"
            />
            <ellipse
              cx="50%"
              cy="80%"
              rx="42%"
              ry="30%"
              fill="none"
              stroke="url(#arc1)"
              strokeWidth="0.5"
            />
          </svg>
        </div>
      </div>

      {/* ── Right: branding + sign-in panel ── */}
      <div className="relative z-20 flex min-h-screen flex-col md:ml-auto md:w-[460px] md:border-l md:border-sidebar-border md:bg-sidebar">
        {/* Top-right branding */}
        <div
          className="flex flex-col items-end px-8 pt-8"
          style={{ animation: "auth-enter 0.7s ease-out 0.1s both" }}
        >
          <h1 className="text-lg font-semibold tracking-tight">prot-cellar</h1>
          <span className="text-xs text-muted-foreground">protein &amp; target platform</span>
        </div>

        {/* Centered sign-in */}
        <div className="flex flex-1 flex-col items-center justify-center">
          <div className="w-full max-w-[320px] px-6 md:px-0">
            <div style={{ animation: "auth-enter 0.7s ease-out 0.2s both" }}>
              <h2 className="text-sm font-medium text-muted-foreground">Sign in to continue</h2>

              <div className="mt-4 flex flex-col gap-3">
                {showGoogle && (
                  <button
                    type="button"
                    onClick={() => login("google")}
                    className="flex w-full cursor-pointer items-center justify-center gap-3 rounded-xl bg-white px-4 py-2.5 text-sm font-medium text-gray-800 transition-all duration-200 hover:-translate-y-px active:translate-y-0 shadow-sm"
                  >
                    <GoogleIcon />
                    Continue with Google
                  </button>
                )}

                {hasEntra && (
                  <button
                    type="button"
                    onClick={() => login("entra")}
                    className="flex w-full cursor-pointer items-center justify-center gap-3 rounded-xl border border-border bg-background px-4 py-2.5 text-sm font-medium text-foreground transition-all duration-200 hover:-translate-y-px active:translate-y-0"
                  >
                    <EntraIcon />
                    Continue with Microsoft
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
