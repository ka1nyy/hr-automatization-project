# HR frontend architecture

The HR workspace is a feature module inside the existing application, not a separate app.

## Layers

- `features/hr/pages`: route-level orchestration and permission-aware views.
- `features/hr/components`: HR navigation and status presentation.
- `features/hr/model`: typed entities and Zod form rules.
- `features/hr/api`: repository contract and mock implementation.
- `features/hr/mocks`: deterministic seed data used only by the mock repository.

Pages depend on `HrRepository`; they do not import fixtures. Replacing `MockHrRepository` with an HTTP implementation therefore does not change page components. The existing app shell, query client, permission system, task/workflow concepts, and visual tokens remain shared.

## Current slice

This branch implements employee records and leave management. Recruitment, staffing, onboarding, performance, transfers, termination, BPMN rendering, and DMN testing are intentionally deferred instead of being represented by empty routes.
