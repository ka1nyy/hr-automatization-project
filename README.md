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

## Hiring Workflow Demo

The development environment includes an end-to-end new employee hiring request. Start it with
`docker compose up -d --build`, then run `npm run dev` in `frontend` and open
`http://localhost:5173`. The backend container automatically applies Alembic migrations and runs
the idempotent development seed. Generated files are stored below the configured
`DOCUMENT_STORAGE_ROOT` (the default Docker volume is not publicly exposed).

Use **Developer tools** in the sidebar to switch between the real seeded database identities:

| Account | Role | Workflow action |
| --- | --- | --- |
| `hr.initiator@demo.local` | Сотрудник HR | Draft, PDF, submit, dispatch |
| `hr.director@demo.local` | Директор HR-департамента | Approval 1 |
| `economic.director@demo.local` | Директор экономического планирования | Approval 2 |
| `commission@demo.local` | Конкурсная комиссия | Approval 3 |
| `legal@demo.local` | Юридический департамент | Approval 4 |
| `chairman@demo.local` | Председатель правления | Approval 5 |
| `accountant@demo.local` | Бухгалтер | Independent receipt acknowledgment |
| `it.specialist@demo.local` | Специалист IT-отдела | Independent receipt acknowledgment |
| `admin@demo.local` (`admin` handle) | Системный администратор | Monitoring and diagnostics |

Local authentication uses the repository's existing development-only `X-Dev-User` adapter, not
frontend mock authentication. It is impossible to enable with production settings, so these
accounts intentionally have no production password. A future OIDC/password provider can map the
same seeded users without changing workflow authorization.

Test the happy path by creating a four-stage form as `hr.initiator`, uploading the identity file
and diploma (the diploma is optional only for “Среднее общее”), generating the server PDF, and
submitting. Switch through the five approvers in order using **Входящие согласования**. After the
Chairman approves, switch back to HR and send the package to Accounting and IT. Each recipient
opens **Документы новых сотрудников** and acknowledges independently; the second acknowledgment
changes the request to `completed`.

To test correction, choose **Вернуть** with a mandatory comment, edit the HR draft, regenerate the
PDF (a new immutable document version is created), and resubmit. To test rejection, choose
**Отклонить** with a reason. Reset all demo data with `docker compose down -v` followed by
`docker compose up -d --build`.

Backend verification commands:

```powershell
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run spk-seed
uv run ruff check app tests
uv run mypy app
uv run pytest
```
