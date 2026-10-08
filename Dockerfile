FROM node:24.16-alpine AS frontend-build

RUN corepack enable && corepack prepare pnpm@11.3.0 --activate

WORKDIR /src/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
ARG VITE_API_BASE_URL=/
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN pnpm build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN pip install --no-cache-dir uv==0.11.28 \
    && uv sync --locked --no-dev --no-install-project

COPY backend/ ./backend/
COPY --from=frontend-build /src/frontend/dist ./frontend/dist/

ENV PATH="/app/.venv/bin:${PATH}" \
    FRONTEND_DIST_DIR=/app/frontend/dist

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
