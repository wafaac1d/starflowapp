FROM node:22-bookworm-slim AS frontend
WORKDIR /src
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/
COPY frontend/ frontend/
COPY resources/ resources/
COPY static/logo.png static/logo.png
COPY static/font static/font
WORKDIR /src/frontend
RUN corepack enable && corepack prepare pnpm@10.18.0 --activate
RUN pnpm install --frozen-lockfile
RUN pnpm build

FROM python:3.12-slim-bookworm AS python-deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ libc6-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin starflow
WORKDIR /app
COPY --from=python-deps /app/.venv /app/.venv
COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations
COPY resources /app/resources
COPY static/logo.png /app/static/logo.png
COPY static/font /app/static/font
COPY --from=frontend /src/frontend/dist /app/frontend/dist
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh && chown -R starflow:starflow /app
USER starflow
ENV PATH="/app/.venv/bin:${PATH}" \
    HOST=0.0.0.0 \
    PORT=8000 \
    WEB_CONCURRENCY=1 \
    PYTHONUNBUFFERED=1 \
    RESOURCES_DIR=/app/resources \
    FRONTEND_DIST=/app/frontend/dist \
    LOGO_PATH=/app/static/logo.png
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
