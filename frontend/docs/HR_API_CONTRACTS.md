# HR API contracts

The typed `HrRepository` is the page-facing contract.

| Method | Suggested HTTP endpoint | Result |
| --- | --- | --- |
| `getOverview()` | `GET /api/hr/overview` | `HrOverview` |
| `listEmployees()` | `GET /api/hr/employees` | `HrEmployee[]` |
| `getEmployee(id)` | `GET /api/hr/employees/:id` | `HrEmployee` |
| `listLeaveRequests()` | `GET /api/hr/leave-requests` | `LeaveRequest[]` |
| `createLeaveRequest(input)` | `POST /api/hr/leave-requests` | `LeaveRequest` |
| `reviewLeaveRequest(id, decision)` | `POST /api/hr/leave-requests/:id/review` | `LeaveRequest` |

Expected errors include `HR_EMPLOYEE_NOT_FOUND`, `HR_LEAVE_BALANCE_EXCEEDED`, `HR_LEAVE_REQUEST_NOT_FOUND`, and `HR_LEAVE_REQUEST_NOT_REVIEWABLE`. The backend should return stable error codes and independently apply role and row-level authorization.
