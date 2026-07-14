# HR feature matrix

| Feature | Route | Persona | Entity | Document | BPMN | Repository | Mock | API ready | Tests | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HR overview | `/departments/hr` | HR specialist | `HrOverview` | None | None | `HrRepository` | Yes | Yes | Indirect | Implemented |
| Employee self-service | `/departments/hr` | Employee | `HrEmployee` | None | None | `HrRepository` | Yes | Yes | Permissions | Implemented |
| Employee directory | `/departments/hr/employees` | HR specialist | `HrEmployee` | Personnel file | None | `HrRepository` | Yes | Yes | Permissions | Implemented |
| Employee profile | `/departments/hr/employees/:id` | HR / owner | `HrEmployee` | Personnel file | None | `HrRepository` | Yes | Yes | Permissions | Implemented |
| Leave submission | `/departments/hr/leave` | Employee | `LeaveRequest` | Leave request | Leave Request v2 | `HrRepository` | Yes | Yes | Unit | Implemented |
| Leave HR review | `/departments/hr/leave` | HR specialist | `LeaveRequest` | Leave request | Leave Request v2 | `HrRepository` | Yes | Yes | Unit | Implemented |
| Recruitment and hiring | Not exposed | HR specialist | Deferred | Deferred | Hiring | None | No | No | No | Deferred |
| Onboarding and offboarding | Not exposed | HR specialist | Deferred | Deferred | Deferred | None | No | No | No | Deferred |
