# Add Employee Frontend

Route: `/hr/hiring/add-employee`.

The page validates the seven requested sections, holds selected files only in memory, saves form JSON to `ertis.hr.add-employee.draft.v1`, renders an official memorandum preview and creates a DOCX in the browser. Clearing removes the local draft. The document contains recipient, initiator, dates, personal/employment/education data, justification, attachment names, signature and resolution areas.

No repository is invoked. Future submission support must implement the documented interface outside the current flow and requires a separate security and backend review.
