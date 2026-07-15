# Frontend integration

Module 1 has no frontend implementation. These conventions are the contract for the later React
and TypeScript application.

## Generate types from OpenAPI

Use `/openapi.json` as the only DTO source. A typical later workflow is:

```powershell
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.d.ts
```

Do not duplicate Python enums manually. Regenerate and review the diff whenever the backend
contract changes.

## Transport conventions

- Base URL: `/api/v1`.
- JSON fields are camelCase.
- Send `Authorization: Bearer <token>` in non-development environments.
- Optionally send a UUID `X-Request-Id`; display returned `requestId` in support/error UI.
- Treat dates (`YYYY-MM-DD`) separately from UTC instants (`...Z`).
- Preserve decimal FTE without binary floating-point rounding in edit forms.
- Send the latest `revision` on every edit/publish/review/revoke/end action.

Success and error envelopes are documented in [API_CONTRACTS.md](API_CONTRACTS.md). A client
interceptor should unwrap `data`, retain `meta`, and map `error.code` to UX behavior while keeping
the server message and request ID visible.

## Organization editor data shape

The active/history response provides a tree-friendly primary structure:

```ts
type UnitNode = {
  id: string;
  stableKey: string;
  code: string;
  name: string;
  unitTypeId: string;
  revision: number;
  children: UnitNode[];
};
```

Additional relationships are a separate flat edge list with source and target IDs. Do not insert
functional/curator arrows into `children`; tree layout and graph overlay are different concepts.

Maintain a normalized client cache keyed by UUID for editing, and derive the visible tree from
`parentUnitId`/`children`. Use `stableKey` for version comparisons, never as the API resource ID.

## Editor save behavior

1. Load a draft and retain each record revision.
2. Send focused mutation requests; do not submit the whole tree for a rename/move.
3. On `CONCURRENCY_CONFLICT`, stop local autosave, reload the stored record, and let the user
   reconcile. Never retry a stale write automatically.
4. Call draft validation and render every returned problem, linking `entityId` to the node/slot.
5. Review and publish actions require a reason; publish also requires an effective date.

The backend remains authoritative for editability, policy, permissions, scope, graph validity,
FTE, and publication state.

An assignment returned as `pending_review` is not yet effective and must not be shown as active
staffing. Organization-scoped HR uses the assignment review endpoint to approve or reject it. A
future scheduled end continues to return effective status `active` through its inclusive
`effectiveTo` date; show the date as scheduled rather than removing authority early.

## Permission-aware interface

Permission summaries may hide or disable controls, but must not be treated as security. Always
handle:

- 401: clear/reacquire identity;
- 403 `AUTH_FORBIDDEN`: capability absent;
- 403 `AUTH_SCOPE_VIOLATION`: target outside the actor's organization/unit scope;
- 409: refresh state and show the stable domain conflict;
- 422: attach field problems or display the complete draft-validation list.

Never branch UI behavior on department/position/employee display names. Use permission codes,
policy fields, status enums, revisions, and stable IDs.

## Sensitive fields

Employee lists never contain IIN, birth date, personal email, or phone. Request a single employee
with `includeSensitive=true` only on a protected view and only when the user has
`employees.read_sensitive`. Do not place sensitive responses in long-lived local storage,
analytics, error telemetry, URLs, or client logs.

## Filtering and pagination

Use server pagination (`page`, `pageSize`) and supported filters/sorts from OpenAPI. Preserve meta
`total` for tables. Debounce text filters and cancel superseded requests. A scoped result's total
means visible records, never organization-global data the actor cannot see.

A staffing slot with status `closing` has a future `effectiveTo`: it remains usable only for
assignments fully contained within that remaining interval. The close workflow requires direct
reporting slots to be reassigned first.
