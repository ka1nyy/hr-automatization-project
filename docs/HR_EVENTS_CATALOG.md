# HR Events Catalog

Allowed event families include employee updates/transfers/termination, leave lifecycle, sick-leave registration/closure, business-trip approval, onboarding/probation updates, offboarding completion and incoming-message read state. Events carry `eventId`, `occurredAt`, `aggregateId`, `correlationId`, version and the minimum necessary payload.

Events are written through the transactional outbox and consumed idempotently. Hiring, Add Employee submission and browser DOCX events are explicitly forbidden.
