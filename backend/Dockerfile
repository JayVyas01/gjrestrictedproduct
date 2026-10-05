# Backend image for the offline demo stack (docker-compose.demo.yml).
# No secrets are baked in: every key and password arrives as an environment variable at run time.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app
# Dependencies first (cached layer), exactly as locked, without the dev tools.
COPY pyproject.toml uv.lock ./
# uv (pinned) is mounted for this step only, so it does not ship in the image.
RUN --mount=from=ghcr.io/astral-sh/uv:0.12.19,source=/uv,target=/bin/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . .
RUN useradd --system --no-create-home --uid 10001 app \
    && chmod 0555 /app/docker-entrypoint.sh
USER app

EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
