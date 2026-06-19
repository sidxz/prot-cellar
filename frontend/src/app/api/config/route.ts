/**
 * Runtime configuration endpoint.
 *
 * Reads environment variables at request time (NOT build time) for
 * environment-specific values, enabling a single universal Docker image.
 *
 * The UI build identity (uiVersion/uiGitSha/uiBuildDate) is image-specific,
 * baked into the image at build time via APP_VERSION/APP_GIT_SHA/APP_BUILD_DATE
 * (see frontend/Dockerfile + publish-images.yml). It is delivered here so the
 * client has a single config-fetch mechanism.
 *
 * Variables use APP_ prefix (server-side only) instead of NEXT_PUBLIC_
 * (which gets baked into the JS bundle at build time).
 *
 * Env var mapping (prot-cellar → chem-cellar equivalent):
 *   APP_API_BASE_URL          ← chem: APP_API_URL
 *   APP_SENTINEL_GOOGLE_CLIENT_ID  ← chem: APP_GOOGLE_CLIENT_ID
 *   APP_SENTINEL_ENTRA_CLIENT_ID   ← chem: APP_ENTRA_ID_CLIENT_ID
 *   APP_SENTINEL_ENTRA_TENANT_ID   ← chem: APP_ENTRA_ID_TENANT_ID
 *   APP_SENTINEL_SERVICE_NAME      ← chem: (no equivalent, new)
 */
export function GET() {
  return Response.json({
    apiBaseUrl: process.env.APP_API_BASE_URL ?? "http://localhost:8001",
    appUrl: process.env.APP_URL ?? "http://localhost:3000",
    sentinelUrl: process.env.APP_SENTINEL_URL ?? "http://localhost:9003",
    serviceName: process.env.APP_SENTINEL_SERVICE_NAME ?? "protcellar",
    idp: {
      googleClientId: process.env.APP_SENTINEL_GOOGLE_CLIENT_ID ?? "",
      entraClientId: process.env.APP_SENTINEL_ENTRA_CLIENT_ID ?? "",
      entraTenantId: process.env.APP_SENTINEL_ENTRA_TENANT_ID ?? "",
    },
    // Build identity (image-specific) + runtime environment (env-specific).
    uiVersion: process.env.APP_VERSION || "0.0.0+dev",
    uiGitSha: process.env.APP_GIT_SHA || "unknown",
    uiBuildDate: process.env.APP_BUILD_DATE || "unknown",
    environment: process.env.APP_ENV || "development",
  });
}
