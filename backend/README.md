# SPK Corporate Backend — Module 1

The backend is a single deployable FastAPI application divided into business modules. Domain
and application code is framework-independent; FastAPI and SQLAlchemy are outer adapters.

## Requirements

- Python 3.12
- PostgreSQL 15 or newer (the local Compose image is PostgreSQL 17)
- Docker Desktop for the container workflow

## Configuration

Copy `.env.example` to `.env`. All settings use the `SPK_` prefix. Important settings are:

| Variable | Purpose |
| --- | --- |
| `SPK_ENVIRONMENT` | `development`, `test`, `staging`, or `production` |
| `SPK_DATABASE_URL` | SQLAlchemy psycopg 3 PostgreSQL URL |
| `SPK_DEV_AUTH_ENABLED` | Enables deterministic development identities only in development |
| `SPK_OIDC_ISSUER` | Expected JWT issuer outside local development |
| `SPK_OIDC_AUDIENCE` | Expected API audience |
| `SPK_OIDC_JWKS_URL` | Provider JWKS URL |
| `SPK_SENSITIVE_DATA_KEY` | Fernet key used to encrypt IIN at rest |

Generate a development-only sensitive-data key in PowerShell:

```powershell
$sensitiveKey = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
(Get-Content .env) -replace '^SPK_SENSITIVE_DATA_KEY=.*$', "SPK_SENSITIVE_DATA_KEY=$sensitiveKey" | Set-Content .env
```

Never reuse a development key in production. Production configuration validation rejects
development authentication and requires a nonblank sensitive-data key and complete OIDC issuer,
audience, and JWKS URL settings. Preserve the configured key while encrypted IIN data exists;
replacing it without a key-rotation migration makes existing values unreadable.

## Development authentication

When `SPK_ENVIRONMENT=development` and `SPK_DEV_AUTH_ENABLED=true`, requests can use the
deterministic `X-Dev-User` values `admin`, `hr`, `director`, `employee`, `reviewer`, `publisher`,
or `auditor`. `admin` is the default in the sample environment. Optional local headers can set
the demonstration organization and unit scope:

```text
X-Dev-User: director
X-Dev-Organization-Id: <uuid>
X-Dev-Unit-Ids: <unit-uuid>[,<unit-uuid>]
```

This adapter cannot be enabled in staging or production. There is no password database or
production persona switcher. Production bearer tokens are verified through the isolated OIDC/JWT
adapter and database authorization remains authoritative.

## Database and seed

```powershell
# repository root
docker compose up -d postgres

# backend directory
alembic upgrade head
python -m app.seed
alembic current
```

The seed is deterministic and safe to re-run. It creates the Module 1 permission catalog, demo
roles, one demonstration organization, reference types, policies, a published structure, units,
and staffing data. The director and employee personas are linked to deterministic employee records
and current assignments. Their scoped operational roles remain narrow; separate read-only,
organization-scoped viewer assignments enable organization navigation. Names are data only;
changing them cannot change authorization behavior.

Production startup runs migrations explicitly. The application never invokes `create_all`.

## Run

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- Liveness: `http://localhost:8000/health/live`
- Readiness: `http://localhost:8000/health/ready`
- API base: `http://localhost:8000/api/v1`

Every response carries a request ID. Send `X-Request-Id` with a UUID to correlate a client request;
otherwise the backend creates one. Logs are structured JSON and intentionally omit request bodies,
tokens, raw IIN, and confidential document contents.

## Test and quality commands

```powershell
pytest
pytest -m integration
ruff check app tests migrations
ruff format --check app tests migrations
mypy app
python -m app.open_api --check
```

Database integration tests use the configured test PostgreSQL database and run migrations before
tests. Unit and API-contract tests do not require external services.

## Design documents

- [Architecture](docs/ARCHITECTURE.md)
- [Domain model](docs/DOMAIN_MODEL.md)
- [API contracts](docs/API_CONTRACTS.md)
- [Permissions](docs/PERMISSIONS.md)
- [Organization versioning](docs/ORGANIZATION_VERSIONING.md)
- [Frontend integration](docs/FRONTEND_INTEGRATION.md)
- [Future modules](docs/FUTURE_MODULES.md)
