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

- complete backend suite: `124 passed`, `0 failed`, `0 skipped`, `1` non-blocking Starlette
  deprecation warning;
- PostgreSQL integration suite: `14 passed`;
- Ruff lint: passed;
- Ruff formatting for configured source/test scope: passed (`216 files already formatted`);
- mypy: passed (`181 source files`);
- clean Alembic migration and double idempotent seed: exercised by the PostgreSQL session fixture;
- OpenAPI contract: exercised by the complete suite, with no contract failures.

The frontend was not changed.
