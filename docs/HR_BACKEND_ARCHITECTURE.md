# HR Backend Architecture

The backend extends the existing NestJS application. HR controllers delegate to services; services enforce policy and transitions; Prisma repositories own persistence. Request middleware supplies actor and correlation context. Audit and outbox writes belong to the same transaction as domain changes.

Practical module boundaries are HR Core, HR Absence and HR Lifecycle. They may remain modules in one deployable until operational scaling justifies separation. Shared Workflow, Document, Task, Notification and Audit systems are accessed only through ports; their databases are never queried directly.

Hiring/Add Employee is deliberately absent from controllers, persistence, workflows and events.
