# HR Database Schema

Current Prisma ownership includes departments, positions, staffing positions, employees, leave balances, leave requests, audit events and outbox events. Records use UUIDs, timestamps, indexes and version fields. Staffing vacancy state describes an organization position and is not a recruitment vacancy feature.

Future additive migrations will introduce service-owned message/receipt, sick leave, business trip, onboarding, probation, employee-change, termination and offboarding tables. Medical details must be isolated from general absence projections. Message read state belongs to `(messageId, userId)` receipts.

No HiringRequest, HiringCase, AddEmployeeDraft or HiringAttachment table may be created by this workstream.
