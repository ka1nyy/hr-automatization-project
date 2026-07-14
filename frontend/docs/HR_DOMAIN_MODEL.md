# HR domain model

## HrEmployee

Identity, employment metadata, manager, department, availability, contract dates, leave balance, personnel-file completeness, skills, and restricted compensation.

## LeaveRequest

Employee, leave period and type, substitute, calculated day count, status, corporate document number, workflow step, and audit events.

## State rules

- New requests start at `pending_manager`.
- HR may act only on `hr_review` requests.
- Approval moves the request to `approved` and deducts the balance once.
- Rejection moves the request to `rejected` without changing the balance.
- A request cannot exceed the current leave balance.

Dates are ISO `YYYY-MM-DD`; timestamps are ISO-8601 UTC strings; money is integer KZT in the current model.
