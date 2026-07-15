# HR Automatization Project

Monorepo for the ERTIS OPERATIONS corporate document management and workflow automation platform.

## Structure

- `frontend/` - React, TypeScript and Vite application with deterministic mock repositories.
- `backend/` - NestJS/Prisma HR backend with employee, dashboard and leave capabilities plus shared workflow/document ports.

## Frontend

```powershell
cd frontend
pnpm install
pnpm dev
```

The frontend opens at `http://localhost:5173` by default. Detailed architecture and release scope are documented in `frontend/docs/`.

## Backend

The backend is included in this branch and remains intentionally free of Hiring/Add Employee APIs. See `docs/HR_HIRING_BACKEND_EXCLUSION.md` for the integration boundary.
