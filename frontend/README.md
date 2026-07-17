# ERTIS OPERATIONS

React frontend for the corporate correspondence, document workflow, organization and HR platform of JSC SPK Ertis. Runtime data comes from the FastAPI backend through `/api/v1`.

## Start locally

Start the database and backend from the repository root, then start Vite:

```powershell
docker compose up -d --build
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Docker does not publish a frontend port; this address belongs only to the Vite development server.

## Quality checks

```powershell
pnpm typecheck
pnpm test
pnpm build
```

Vite proxies `/api` to the backend published by Docker Compose on `http://127.0.0.1:8000`. The production build uses same-origin `/api/v1`, so no browser-visible backend address is embedded in the bundle.

## HR workspace

Select `Зарина Ахметова / HR специалист` to test HR operations or an employee persona to test self-service. Permissions and all business mutations are enforced by the backend.
