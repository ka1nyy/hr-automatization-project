# HR Testing

Every increment runs frontend typecheck/lint/tests/build and backend typecheck/lint/unit/e2e/build. Frontend coverage includes HR header context, terminology and absent ATS surfaces, Add Employee validation/local draft/preview/DOCX without network, repository mapping, optimistic message state and privacy-aware screens.

Backend coverage includes permission/ABAC rules, validations, optimistic locking, per-user receipts, privacy projections, audit/outbox transactions and absence/lifecycle transitions. E2E must explicitly prove forbidden Hiring endpoints return 404 and browser DOCX generation creates no request. Browser QA covers exact `/hr/*` routes, mobile/desktop layouts, light/dark themes and console errors.
