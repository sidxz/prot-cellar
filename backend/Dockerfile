FROM python:3.13-slim

WORKDIR /app

RUN apt-get update \
  && apt-get upgrade -y --no-install-recommends \
  && rm -rf /var/lib/apt/lists/*

# uv owns the venv; the base image's pip (and the wheels ensurepip carries)
# only add a dependency tree that scanners flag and nothing at runtime uses.
RUN python -m pip uninstall -y pip \
  && rm -rf /usr/local/lib/python3.13/ensurepip /root/.cache/pip

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies first (layer caching) — project itself not yet installed
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code, then install the project so `protcellar` is importable
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .
RUN uv sync --frozen --no-dev

RUN adduser --disabled-password --uid 1000 protcellar
USER protcellar

# Build identity — injected by CI from the git tag (see publish-images.yml).
# Defaults keep local `docker build` runs honest about being unversioned.
ARG APP_VERSION=0.0.0+dev
ARG APP_GIT_SHA=unknown
ARG APP_BUILD_DATE=unknown
ENV APP_VERSION=$APP_VERSION \
    APP_GIT_SHA=$APP_GIT_SHA \
    APP_BUILD_DATE=$APP_BUILD_DATE

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

CMD [".venv/bin/uvicorn", "protcellar.interface.app:app", "--host", "0.0.0.0", "--port", "8001", "--no-server-header"]
