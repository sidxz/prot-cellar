# Releasing prot-cellar

The frontend and backend are versioned **independently** with **SemVer**, and
the **git tag is the single source of truth**. CI builds the image, injects the
version, and publishes a changelog + GitHub Release.

## Tag namespaces

| Component | Tag form          | Image                                       |
|-----------|-------------------|---------------------------------------------|
| Backend   | `backend-vX.Y.Z`  | `ghcr.io/sidxz/prot-cellar-backend:X.Y.Z`   |
| Frontend  | `frontend-vX.Y.Z` | `ghcr.io/sidxz/prot-cellar-frontend:X.Y.Z`  |

Pushing a tag in one namespace builds, tags, and releases **only** that
component. Pushes to `main` still publish `:latest` and `:sha-<sha>` images for
whichever component changed.

**Pre-releases** (`backend-v0.1.0-beta.1`) get only their exact image tag
(`0.1.0-beta.1`) and a GitHub Release marked *pre-release*; the floating `X.Y`
and `X` tags move on stable releases only.

## Choosing the bump (Conventional Commits)

Look at the commits since the component's previous tag:

| Commit type                          | Bump   |
|--------------------------------------|--------|
| `fix:`                               | patch  |
| `feat:`                              | minor  |
| `feat!:` / `BREAKING CHANGE:` footer | major  |

A backend **major** bump signals a breaking API change — the moment to check the
frontend is compatible.

## Cutting a release

1. Make sure `main` is green and pulled locally.
2. Run the security gate locally and make sure it passes:
   ```bash
   make security-scan   # Trivy: lockfiles, secrets, then both images
   ```
   It fails on any fixable HIGH/CRITICAL finding. Fix the dependency or base
   image; only add an id to a `.trivyignore` file, with the reason, when the
   code cannot run or the fix is a scheduled major. Never tag over a red scan.
3. Pick the next version per the table above. Inspect what changed:
   ```bash
   # commits touching the backend since its last tag
   git log "$(git tag --list 'backend-v*' --sort=-creatordate | head -1)"..HEAD -- backend/
   ```
4. Tag and push:
   ```bash
   git tag backend-v1.4.0      # or frontend-v2.1.0, or backend-v0.1.0-beta.1
   git push origin backend-v1.4.0
   ```
5. CI (`.github/workflows/publish-images.yml`) then:
   - builds **only** that component and tags the image `1.4.0`, `1.4`, `1`;
   - injects `APP_VERSION` / `APP_GIT_SHA` / `APP_BUILD_DATE` into the image — all three
     come from `scripts/build-info.sh <component>`, the single derivation shared with `make dev`;
   - generates a `git-cliff` changelog scoped to that component since its
     previous tag and publishes a **GitHub Release** ("Backend v1.4.0").

If a newly published image can't be pulled without logging in, set the
package's visibility to *Public* (GitHub → Packages → the package → Package
settings). prot-cellar's two packages came out public on their first push.

## Deploying

On the host, next to `docker-compose.infra.yml` and `docker-compose.prod.yml`:

```bash
cp .env.example .env               # fill in Duar values, POSTGRES_PASSWORD, PROT_CELLAR_TAG
make prod-pull && make prod-up     # migrate runs first; backend :8001, frontend :3001
make prod-logs
```

To try the exact stack from local source before tagging:

```bash
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml -f docker-compose.yml up -d --build
```

## Where the version shows up

- **App UI:** the sidebar version tag, and **Settings** — UI version + commit +
  build date from the baked image, the live API version (`GET /version`), and
  the environment.
- **Backend `GET /version`:** unauthenticated JSON
  `{version, git_sha, build_date, environment}` — handy for `curl`/monitoring.

## Between releases

Builds between tags identify as the `git describe` form, e.g.
`1.4.0-128-g84e7848` — base tag, commits ahead, short sha. That is expected and
honest: it is not a clean release.

## Not the source of truth

`backend/pyproject.toml` and `frontend/package.json` carry a placeholder version
that **nothing displays**. The git tag is authoritative; there is nothing to bump
in those files when releasing. Locally, `make dev` exports the same identity the
image would get (`scripts/build-info.sh` → `git describe` against the nearest
`<component>-v*` tag); with no tag at all both apps show `0.0.0+dev` / `unknown`.
