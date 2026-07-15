# HR Security Model

Permissions use the `hr.*` namespace and are evaluated with record attributes. Directory reads distinguish self, team and all. Personal, compensation and medical access are independent permissions. Manager sick-leave projections expose dates and availability only.

Sensitive values are omitted rather than masked ambiguously. Personal, medical and compensation access is auditable. Logs contain IDs, action, result and correlation metadata, never IIN, diagnosis, certificate details, salary or form attachment contents.
