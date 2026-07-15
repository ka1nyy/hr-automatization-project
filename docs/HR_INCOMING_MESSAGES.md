# HR Incoming Messages

Incoming messages are corporate communications addressed to HR and are classified `EXTERNAL` or `INTERNAL`. Message content and user-specific receipts are separate. A receipt uniquely identifies message and user, with read time and version.

The list contract supports source, read state, sender, organization/department type, priority, attachments, related employee/process, dates, search, sort and pagination. Read/unread updates are optimistic in the frontend with rollback and server-calculated per-user counters.
