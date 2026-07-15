# ERTIS OPERATIONS

React frontend for the corporate correspondence, document workflow, organization and HR platform of JSC SPK Ertis. Runtime data comes from the FastAPI backend through `/api/v1`.

## Start locally

Start PostgreSQL and backend from the repository root, then start Vite:

```powershell
docker compose up -d postgres backend
cd frontend
pnpm install
pnpm dev
```

Open `http://localhost:5173`. Run all commands from the `frontend` directory.

## Quality checks

```powershell
pnpm typecheck
pnpm test
pnpm build
```

Vite proxies `/api` to the backend on `http://localhost:8000`. Production nginx proxies the same path to the backend service, so no browser-visible localhost API address is embedded in the build.

## HR workspace

Select `Зарина Ахметова / HR специалист` to test HR operations or an employee persona to test self-service. Permissions and all business mutations are enforced by the backend.
