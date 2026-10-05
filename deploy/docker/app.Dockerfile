# One image for every Fleetwright backend process (API, gateway, control, worker, mock board,
# migrations, seed). The base is Playwright's Python image: it carries Chromium and its system
# libraries at the same Playwright version uv.lock pins, so the worker needs nothing extra.
# Build context: the repository root (see .dockerignore).
FROM ghcr.io/astral-sh/uv:0.12.10@sha256:2bb3ebca0a796a155094a27773d290c4b074572e6107f171d88d086682fd2500 AS uv

FROM mcr.microsoft.com/playwright/python:v1.63.0-noble@sha256:72bd171a9ffc2b4b59532aaa6210e21014d07093120dc25528870c0b840da1f0
COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.12 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages packages
COPY apps/coordinator apps/coordinator
COPY apps/gateway apps/gateway
COPY apps/mockboard apps/mockboard
COPY apps/worker apps/worker
RUN uv sync --frozen --no-dev --no-editable && rm -rf /root/.cache/uv
COPY config config
# Named volumes copy this ownership on first use, so the non-root user can write evidence.
RUN mkdir -p /data/evidence && chown pwuser:pwuser /data/evidence

ENV PATH=/app/.venv/bin:$PATH \
    FW_CONFIG_DIR=/app/config \
    HOME=/tmp
USER pwuser
