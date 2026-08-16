import type { AppConfig } from "@/shared/lib/app-config";
import {
  AuthzLocalStorageStore,
  type IdpConfig,
  IdpConfigs,
  DuarAuthz,
} from "@duar-auth/js";

function buildIdps(config: AppConfig): Record<string, IdpConfig> {
  const idps: Record<string, IdpConfig> = {};
  if (config.idp.googleClientId) {
    idps.google = IdpConfigs.google(config.idp.googleClientId);
  }
  if (config.idp.entraClientId && config.idp.entraTenantId) {
    idps.entraId = IdpConfigs.entraId(config.idp.entraClientId, config.idp.entraTenantId);
  }
  return idps;
}

let _client: DuarAuthz | null = null;

/**
 * Create (or return cached) DuarAuthz client.
 * Accepts runtime AppConfig so no process.env is read at module load.
 */
export function getDuarClient(config?: AppConfig): DuarAuthz {
  if (!_client) {
    const duarUrl = config?.duarUrl ?? "http://localhost:9003";
    const appUrl = config?.appUrl ?? "http://localhost:3001";

    _client = new DuarAuthz({
      duarUrl,
      idps: config ? buildIdps(config) : {},
      redirectUri: `${appUrl}/auth/callback`,
      // Required since Duar 0.11.0: the browser no longer mints authz tokens
      // directly. It POSTs to this same-origin backend route, which forwards to
      // Duar's /authz/resolve with the service key. See app/api/auth/mint.
      mintEndpoint: "/api/auth/mint",
      storage: typeof window !== "undefined" ? new AuthzLocalStorageStore() : undefined,
      autoRefresh: true,
      refreshBuffer: 30,
    });
  }
  return _client;
}

/**
 * Return auth headers for the current Duar session.
 * Returns an empty object when no client has been initialised (SSR / tests).
 * Consumed by custom-instance.ts (Task 5) and its vitest mock.
 */
export function getAuthHeaders(): Record<string, string> {
  if (!_client) return {};
  return _client.getHeaders();
}
