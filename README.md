# HR Automatization Project

ERTIS OPERATIONS combines this repository's React HR frontend with a modular FastAPI backend for
identity, access control, organization structures, staffing, employees, configurable employee
functions, workflow, documents, recruitment, hiring, termination/offboarding, immutable audit and
transactional integration events. The frontend from `spk-corporate-system` is not included.

## Start locally

From the repository root:

```powershell
docker compose up -d --build
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Docker Compose starts PostgreSQL and FastAPI only. It applies Alembic migrations, seeds the development organization, and publishes the backend on `http://localhost:8000`. The frontend is served exclusively by Vite, so Docker does not create a second copy of the site.

Stop the application with:

```powershell
docker compose down
```

## Development ports

- `http://localhost:5173` — Vite frontend started by `npm run dev`.
- `http://localhost:8000` — FastAPI backend started by Docker Compose.
- `http://localhost:8000/health/ready` — backend readiness check.

Vite proxies `/api` to `http://127.0.0.1:8000`, so the browser and backend use one development flow without CORS workarounds.

If `8000` is occupied by another project, override the backend host port and update the Vite proxy target accordingly:

```powershell
$env:BACKEND_PORT = "8080"
docker compose up -d --build
```

See [backend/README.md](backend/README.md) for configuration, authentication, migration, seed,
and test details. Architecture and API documents are in [backend/docs](backend/docs).

## Scope boundary

Module 2 implements its workflow runtime locally; it does not pretend that Camunda, electronic
signature, job boards, IAM, payroll, or asset systems are connected. Those actions are explicit,
auditable manual/external-verification tasks behind adapter boundaries. Leave, time accounting,
payroll calculation, transfers, and a universal low-code engine remain outside this module.
