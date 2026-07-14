# HR mock scenarios

Select personas from the existing developer panel.

## HR specialist

Use `Зарина Ахметова / HR специалист` to open the workforce overview, search the employee directory, inspect personnel records and compensation, and review `HR-LV-2026-0102`.

## Employee

Use `Мадина Садыкова / Сотрудник` to view only the personal HR overview and submit a leave request. A valid request generates an `HR-LV-2026-*` document number, workflow step, and audit event. A request above the displayed balance is rejected.

Data persists under localStorage key `ertis-hr-mock-v1`. The existing Reset action clears both the core and HR mock databases.
