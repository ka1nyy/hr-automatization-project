# HR Frontend Architecture

HR remains a feature area inside the shared React application. `DepartmentProvider` derives the department, permissions and page label from the authenticated user (represented by the selected development persona locally), rather than from an HR URL alone. An HR user lands on `/`, where the ordinary dashboard slot renders HR Home. `AppShell` then composes the existing sidebar with HR-relevant shared and feature routes; there is no separate nested “HR Workspace” application. `/hr/*` remains canonical for HR-specific feature pages and legacy routes remain compatible during migration. Pages reuse `AppShell`, `PageHeader`, `Section`, form controls, tokens and responsive rules.

Shared pages keep their service ownership. Incoming Messages reuses correspondence repositories, Tasks reuses the task gateway, Processes reuses workflow definitions, and Organization reuses the corporate directory. Each page reads department context to show `HR / Current Page` and department-relevant labels or projections without duplicating the shared service.

Backend state belongs to TanStack Query repositories. Each backend-connected feature will expose DTOs, domain types, mapper, API adapter and mock adapter. Zustand remains limited to developer/theme UI state. Page components must not import fixtures.

Add Employee is isolated under `features/hr/add-employee`. Its form uses React Hook Form and Zod, keeps attachments in memory, stores only JSON values in localStorage, previews locally and generates DOCX with `docx`. `AddEmployeeSubmissionRepository` is a future interface and is neither implemented nor invoked.
