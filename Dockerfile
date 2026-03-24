# ---- Base: install Python deps ----
FROM python:3.11-slim AS base

RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ---- Backend: API server ----
FROM base AS backend
COPY backend/ backend/
COPY alembic/ alembic/
COPY alembic.ini .
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---- Celery: task worker ----
FROM base AS celery-worker
COPY backend/ backend/
CMD ["uv", "run", "celery", "-A", "backend.workers.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
