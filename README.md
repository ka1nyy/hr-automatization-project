# HR Automatization Project

ERTIS OPERATIONS combines the modular SPK FastAPI backend with the React HR and document-workflow frontend.

## Start the complete application

From the repository root:

```powershell
docker compose up --build
```

Open `http://localhost:5173`. This starts PostgreSQL, applies Alembic migrations, seeds the development organization, starts the backend, and serves the frontend through nginx. Browser requests use the same-origin `/api/v1` route; nginx forwards them to the backend.

Stop the application with:

```powershell
docker compose down
```

## Frontend development

Start PostgreSQL and the backend first, then run Vite:

```powershell
docker compose up -d postgres backend
cd frontend
pnpm install
pnpm dev
```

Vite proxies `/api` to `http://localhost:8000`, so the browser never needs a hard-coded backend origin.
