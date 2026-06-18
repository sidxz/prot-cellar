FROM python:3.13-slim

WORKDIR /app

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
ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown
ENV PROTCELLAR_VERSION=$APP_VERSION \
    PROTCELLAR_GIT_SHA=$GIT_SHA \
    PROTCELLAR_BUILD_DATE=$BUILD_DATE

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

CMD [".venv/bin/uvicorn", "protcellar.interface.app:app", "--host", "0.0.0.0", "--port", "8001", "--no-server-header"]
