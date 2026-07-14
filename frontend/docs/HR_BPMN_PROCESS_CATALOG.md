# HR BPMN process catalog

| Process | Current frontend integration | Status |
| --- | --- | --- |
| Leave Request v2 | Request stores current workflow step and audit trail | Mock vertical slice |
| Sick Leave | None | Deferred |
| Hiring | None | Deferred |
| Onboarding | None | Deferred |
| Employee Change | None | Deferred |
| Termination / Offboarding | None | Deferred |

The current repository simulates process state but does not render BPMN or call Camunda. A production repository should map workflow task IDs and incidents while preserving the page-facing contract.
