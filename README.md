# HR Automatization Project

ERTIS OPERATIONS combines this repository's React HR frontend with a modular FastAPI backend for
identity, access control, organization structures, staffing, employees, configurable employee
functions, workflow, documents, recruitment, hiring, termination/offboarding, leave, business
trips, immutable audit and transactional integration events. The frontend from
`spk-corporate-system` is not included.

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

See [backend/README.md](backend/README.md) for configuration, authentication, migration, seed,
and test details. Architecture and API documents are in [backend/docs](backend/docs).

## Scope boundary

The backend implements its workflow runtime locally; it does not pretend that Camunda, electronic
signature, job boards, IAM, payroll, or asset systems are connected. Those actions are explicit,
auditable manual/external-verification tasks behind adapter boundaries. Leave, time accounting,
payroll calculation, transfers, and a universal low-code engine remain outside this module.
