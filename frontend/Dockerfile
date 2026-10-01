FROM node:22-alpine AS base
# pnpm version is pinned via the packageManager field in package.json;
# corepack resolves it per-project so Docker/CI/local all use the same version.
RUN corepack enable

FROM base AS deps
WORKDIR /app
# pnpm-workspace.yaml carries the allowBuilds approvals — without it pnpm
# refuses to run dependency build scripts and install fails (ERR_PNPM_IGNORED_BUILDS).
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production

# Build identity — injected by CI from the git tag (see publish-images.yml).
# Image-specific (not environment-specific), so baking as ENV is correct; the
# Node server reads these at runtime and serves them from /api/config.
ARG APP_VERSION=0.0.0+dev
ARG APP_GIT_SHA=unknown
ARG APP_BUILD_DATE=unknown
ENV APP_VERSION=$APP_VERSION \
    APP_GIT_SHA=$APP_GIT_SHA \
    APP_BUILD_DATE=$APP_BUILD_DATE

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

# The runtime needs node only. npm, corepack and pnpm come with the base image
# and carry their own dependency trees, which is where most image CVEs land.
RUN rm -rf /usr/local/lib/node_modules /usr/local/bin/npm /usr/local/bin/npx \
  /usr/local/bin/corepack /usr/local/bin/pnpm /usr/local/bin/pnpx

RUN adduser -D -u 1001 protcellar
USER protcellar

# Docker sets HOSTNAME to the container id; Next's standalone server binds to
# it, which would leave loopback (the healthcheck) unanswered.
ENV HOSTNAME=0.0.0.0

EXPOSE 3000

# 127.0.0.1, not localhost: alpine resolves localhost to ::1 first, and the
# server listens on IPv4 only.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3000/api/config || exit 1

CMD ["node", "server.js"]
