# ── Build stage ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (better layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies into /app/.venv (no-sync = use lock file exactly)
RUN uv sync --frozen --no-dev

# ── Runtime stage ─────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Copy the pre-built venv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY main.py ./
COPY src/ ./src/

# Token storage directory (mount a volume here to persist OAuth tokens)
RUN mkdir -p /app/tokens

# Make venv the active Python
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 4325

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4325"]
