# --- Build stage: resolve the locked dependencies into a self-contained virtualenv ---
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Only the manifests, so this layer stays cached until dependencies actually change
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev


# --- Runtime stage: just the interpreter, the virtualenv and the script ---
FROM python:3.13-slim

COPY --from=builder /app/.venv /app/.venv

WORKDIR /app
COPY hass_backup_decrypt.py ./

RUN mkdir -p /input /output

# No USER directive on purpose: the documented run passes --user=$(id -u):$(id -g) so the
# decrypted files end up owned by the invoking user rather than by root.
ENTRYPOINT ["/app/.venv/bin/python", "/app/hass_backup_decrypt.py"]
