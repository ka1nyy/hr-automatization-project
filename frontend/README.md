# ERTIS OPERATIONS

First operational frontend release for the corporate correspondence, document workflow and department operations platform of JSC SPK Ertis.

The application opens directly into a developer workspace. It uses deterministic mock repositories and requires no backend or authentication.

## Start locally

```powershell
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

## Runtime modes

The current release implements mock mode. API, Camunda and signature adapter boundaries are documented and intentionally contain no secrets.

```env
VITE_DATA_MODE=mock
VITE_WORKFLOW_MODE=mock
VITE_SIGNATURE_MODE=mock
VITE_NUMBERING_MODE=mock
VITE_DEFAULT_LOCALE=ru
```

See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for the exact v1.0.1 scope.

## HR workspace

The `hr-department` branch adds a frontend-only HR vertical slice at `/departments/hr`. Select `Зарина Ахметова / HR специалист` to test HR operations or `Мадина Садыкова / Сотрудник` to test employee self-service. The mock data is deterministic and the Reset action restores its initial state.

See [docs/HR_IMPLEMENTATION_PLAN.md](docs/HR_IMPLEMENTATION_PLAN.md) and [docs/HR_FEATURE_MATRIX.md](docs/HR_FEATURE_MATRIX.md) for implemented and deferred scope.
