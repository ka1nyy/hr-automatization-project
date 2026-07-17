# Add Employee Frontend

## Purpose and route

`/hr/hiring/add-employee` creates and submits the official hiring application. It does not create an employee account directly. The shared application shell, HR permission model and existing panel/form/dialog styles are reused.

## Form and validation

The wizard contains four steps: personal data, proposed employment, education and experience, and required documents. Reference values come from `referenceData.ts`.

Zod enforces required fields, a 12-digit IIN, email and phone formats, past date of birth, a reasonable start date, identity expiry after issue, non-negative salary/probation and FTE limits. Attachments accept PDF, DOC, DOCX, JPG and PNG up to 10 MB. The identity document is always required; a diploma is required unless the selected education level is secondary general education.

## Draft lifecycle

`ertis.hr.add-employee.draft.v1` stores `{ values, savedAt }` in localStorage. Files are deliberately excluded. Saving also persists the server draft. Clear Form requires confirmation and removes form values, selected files and the local draft.

## Submission and PDF

The final action is `Отправить заявление`. One click validates the full form and required files, saves the server draft, uploads the attachments, generates a versioned PDF and submits the request to the sequential approval route.

The PDF contains the addressee and initiator, request text, complete personal and identity data, proposed employment, compensation and justification, education and experience, attachment names, the approval sheet, confidentiality marking and page numbering. The generated version remains available from the application and request details screens.

The approval route is:

1. Director of the document management and HR department.
2. Director of economic planning.
3. Competition commission.
4. Legal department.
5. Chairman of the board.

After final approval, an authorized initiator sends the final PDF package to Accounting and IT from the request details page. Recipients acknowledge receipt in their queue.

## Architecture

React Hook Form owns local form state. `schema.ts`, `referenceData.ts`, `defaults.ts`, `draft.ts` and `utils.ts` keep validation and local persistence out of the page. `hiringRequests.ts` maps every form field to the backend contract. The backend stores restricted document versions and renders the official PDF with ReportLab.
