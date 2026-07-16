# Project handoff

## Repository state

- Repository: `https://github.com/ka1nyy/hr-automatization-project.git`
- Branch: `codex/module2-recruitment-hiring-termination`
- Starting commit: `fbc3a22d81f61a3a678d3918f06875d459c476ec`

## Workflow synchronization

Specialized recruitment, hiring, and termination operations now update their linked generic
workflow in the same SQLAlchemy transaction. The shared workflow adapter accepts the caller's
`AsyncSession`, locks the `ProcessInstance` and active `WorkflowTask`, validates the snapshot phase
and eligible actor, applies sequential or parallel completion rules, creates the next tasks, and
records process history and transactional outbox events before the business transaction commits.

The integration covers recruitment HR/staffing decisions and resubmission, hiring terminal
completion and cancellation, and termination review, return/resubmission, completion, and
cancellation. Return keeps the process active and reopens the returned task on resubmission;
rejection and cancellation close unfinished tasks. Terminal hiring and termination operations
cannot leave active generic tasks. Linked action keys make repeated specialized review requests
idempotent, while row and process locks preserve optimistic-concurrency behavior.

Actor selection uses the workflow definition snapshot and existing actor rules. If a specialized
actor is an eligible permission holder but another eligible holder received the original sequential
assignment, the task is atomically assigned to the acting eligible user. Ineligible and cross-scope
actors remain rejected. Transitions continue to use `ProcessInstance.definition_version_id`, so
instances started under older published definitions are not moved to a newer definition.

## Verification

Verified on a dedicated PostgreSQL 17 database (`spk_hr_test`):

- complete backend suite: `138 passed`, `0 failed`, `0 skipped`, `1` non-blocking Starlette
  deprecation warning;
- PostgreSQL integration suite: `17 passed`;
- Ruff lint: passed;
- Ruff formatting for configured source/test scope: passed (`227 files already formatted`);
- mypy: passed (`190 source files`);
- clean Alembic upgrade to `0005_absence`: passed;
- Alembic metadata drift check: `No new upgrade operations detected`;
- idempotent seed: passed twice;
- OpenAPI contract: `136 paths`, with no contract failures.

The frontend was not changed.

## Module 4 increment: leave and business trips

The `absence` bounded context adds annual/unpaid leave types, per-year balances, leave requests,
and business-trip requests. Leave reserves entitlement on submission and moves the reservation to
used days only after final HR approval. Invalid dates, insufficient balances and overlapping active
leave/trip periods fail before any process, audit or outbox state is committed.

Leave uses manager and HR workflow stages. Business trips use manager, finance and HR-registration
stages. Both support return to the exact prior stage, resubmission, rejection, cancellation,
idempotent decisions, optimistic concurrency and actor/scope resolution through existing RBAC.
Alembic head is `0005_absence`.

The employee workspace's `employee_absences` table is the calendar/read projection, while
`leave_requests` and `business_trip_requests` remain the approval aggregates. Final leave approval
or trip registration creates that projection in the same transaction; cancellation updates it.
`source_type` plus `source_id` makes projection creation idempotent. The `0005_absence` migration
also merges the formerly competing `0004_module2` and `0004_employee_absences` Alembic branches,
leaving exactly one head.

Frontend verification for the employee-absence UI already present on `main`: ESLint passed,
TypeScript passed, `22` tests passed, and the production Vite build passed.
