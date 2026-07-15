# HR Automatization Project

ERTIS OPERATIONS combines the modular SPK FastAPI backend with this repository's React HR and document-workflow frontend. The frontend from `spk-corporate-system` is intentionally not included.

## Start the complete application

From the repository root:

```powershell
docker compose up --build
```

Open `http://localhost:5173`. Docker Compose starts one application container plus an internal PostgreSQL service. The application image builds this repository's React frontend, applies Alembic migrations, seeds the development organization, starts FastAPI, and serves both the UI and same-origin `/api/v1` from one process and one exposed port.

Stop the application with:

```powershell
docker compose down
```

## Frontend development

Start PostgreSQL and the combined application first, then run Vite if you need hot reload:

```powershell
docker compose up -d postgres app
cd frontend
pnpm install
pnpm dev
```

Vite proxies `/api` to `http://localhost:8000`, so the browser never needs a hard-coded backend origin.
