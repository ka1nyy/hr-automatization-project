# HR route matrix

| Route | HR specialist | Employee | Purpose |
| --- | --- | --- | --- |
| `/departments/hr` | HR metrics and review queue | Personal overview and balance | Role-aware entry page |
| `/departments/hr/employees` | Allowed | Denied | Searchable employee directory |
| `/departments/hr/employees/:employeeId` | Any employee | Own profile only | Personnel profile |
| `/departments/hr/leave` | Review queue | Create and track own requests | Leave workflow |

The HR navigation item is shown only to personas with `hr.read`. Unknown HR routes use the existing application fallback.
