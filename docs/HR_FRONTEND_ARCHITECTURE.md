# HR Frontend Architecture

HR remains a feature area inside the shared React application. `DepartmentProvider` derives the authenticated workspace context and page label. `/hr/*` is canonical; legacy routes remain compatible during migration. Pages reuse `AppShell`, `PageHeader`, `Section`, form controls, tokens and responsive rules.

Backend state belongs to TanStack Query repositories. Each backend-connected feature will expose DTOs, domain types, mapper, API adapter and mock adapter. Zustand remains limited to developer/theme UI state. Page components must not import fixtures.

Add Employee is isolated under `features/hr/add-employee`. Its form uses React Hook Form and Zod, keeps attachments in memory, stores only JSON values in localStorage, previews locally and generates DOCX with `docx`. `AddEmployeeSubmissionRepository` is a future interface and is neither implemented nor invoked.
