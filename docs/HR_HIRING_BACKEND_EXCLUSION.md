# Hiring Backend Exclusion

## What exists now

The frontend provides a complete Add Employee form, validation, local preview, browser DOCX download and local draft metadata. Attachments remain in memory and are listed by name in the document.

## What is excluded

This workstream must not create Hiring APIs, database tables, microservices, events, Camunda processes/workers, tasks, server drafts, attachment uploads, employee creation from this form or server-side DOCX generation. In particular, these endpoints must not exist: `POST /api/v1/hr/hiring`, `POST /api/v1/hr/add-employee`, `POST /api/v1/hr/hiring-requests`.

## Future owner and boundary

Another engineer owns any future Hiring backend. The interface `AddEmployeeSubmissionRepository.submit(values)` documents the UI boundary only. There is deliberately no API adapter, dependency injection binding or call site. A future integration must define consent, field-level authorization, attachment storage, idempotency, workflow, audit, retention and error contracts before enabling submission.
