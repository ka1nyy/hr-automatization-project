FROM node:22-alpine AS frontend-build

WORKDIR /build/frontend
RUN corepack enable

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=${VITE_API_URL}
RUN pnpm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SPK_FRONTEND_DIST_PATH=/srv/app/frontend-dist

WORKDIR /srv/app

COPY backend/pyproject.toml backend/README.md ./
COPY backend/app ./app
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations

RUN pip install --upgrade pip && pip install .

COPY --from=frontend-build /build/frontend/dist ./frontend-dist

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /srv/app
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

