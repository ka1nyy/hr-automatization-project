# HR permission matrix

| Permission | HR specialist | Employee |
| --- | --- | --- |
| `hr.read` | Yes | Yes |
| `hr.employees.read` | Yes | No |
| `hr.sensitive.read` | Yes | No |
| `hr.leave.create` | Yes | Yes |
| `hr.leave.review` | Yes | No |

Compensation is rendered only with `hr.sensitive.read`. Employee profile access is additionally scoped to the current employee record. The frontend checks improve UX; the future backend must enforce the same rules.
