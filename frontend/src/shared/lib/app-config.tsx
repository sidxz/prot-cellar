"use client";

import { type ReactNode, createContext, useContext } from "react";

export interface AppConfig {
  apiBaseUrl: string;
  appUrl: string;
  sentinelUrl: string;
  serviceName: string;
  idp: {
    googleClientId: string;
    entraClientId: string;
    entraTenantId: string;
  };
  uiVersion: string;
  uiGitSha: string;
  uiBuildDate: string;
  environment: string;
}

const defaultConfig: AppConfig = {
  apiBaseUrl: "http://localhost:8001",
  appUrl: "http://localhost:3000",
  sentinelUrl: "http://localhost:9003",
  serviceName: "protcellar",
  idp: {
    googleClientId: "",
    entraClientId: "",
    entraTenantId: "",
  },
  uiVersion: "0.0.0+dev",
  uiGitSha: "unknown",
  uiBuildDate: "unknown",
  environment: "development",
};

const AppConfigContext = createContext<AppConfig>(defaultConfig);

export function AppConfigProvider({
  config,
  children,
}: {
  config: AppConfig;
  children: ReactNode;
}) {
  return <AppConfigContext.Provider value={config}>{children}</AppConfigContext.Provider>;
}

export function useAppConfig(): AppConfig {
  return useContext(AppConfigContext);
}

/**
 * Fetch runtime config from the server endpoint.
 * Falls back to defaults when server not reachable (SSR, tests).
 */
export async function fetchAppConfig(): Promise<AppConfig> {
  try {
    const res = await fetch("/api/config");
    if (res.ok) return await res.json();
  } catch {
    // Server not reachable (SSR, tests) — fall through to defaults
  }

  return defaultConfig;
}
