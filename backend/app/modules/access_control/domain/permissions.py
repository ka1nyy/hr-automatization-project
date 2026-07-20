"""Stable permission identifiers exposed by Module 1."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PermissionDefinition:
    code: str
    name: str
    description: str


PERMISSION_CATALOG: tuple[PermissionDefinition, ...] = (
    PermissionDefinition("organization.read", "Read organization", "View organization details."),
    PermissionDefinition(
        "organization.structure.read",
        "Read organization structures",
        "View current and historical structures.",
    ),
    PermissionDefinition(
        "organization.structure.draft.create",
        "Create structure drafts",
        "Create a draft structure version.",
    ),
    PermissionDefinition(
        "organization.structure.edit",
        "Edit structure drafts",
        "Edit an organization structure draft.",
    ),
    PermissionDefinition(
        "organization.structure.review",
        "Review structure drafts",
        "Submit, approve, or return a draft.",
    ),
    PermissionDefinition(
        "organization.structure.publish",
        "Publish structures",
        "Publish a validated structure version.",
    ),
    PermissionDefinition(
        "organization.unit.manage", "Manage units", "Create, edit, move, and deactivate units."
    ),
    PermissionDefinition(
        "organization.relationship.manage",
        "Manage relationships",
        "Maintain additional organization relationships.",
    ),
    PermissionDefinition(
        "organization.staffing.manage", "Manage staffing", "Create, edit, and close staffing slots."
    ),
    PermissionDefinition("employees.read", "Read employees", "View non-sensitive employee data."),
    PermissionDefinition(
        "employees.read_sensitive",
        "Read sensitive employee data",
        "View explicitly protected employee fields.",
    ),
    PermissionDefinition("employees.create", "Create employees", "Create employee draft records."),
    PermissionDefinition("employees.edit", "Edit employees", "Edit employee records."),
    PermissionDefinition(
        "employees.assign", "Assign employees", "Create and end employee assignments."
    ),
    PermissionDefinition(
        "employees.hire",
        "Hire employees",
        "Run the hire business function: create an employment record with an assignment.",
    ),
    PermissionDefinition(
        "employees.terminate",
        "Terminate employees",
        "Run the terminate business function: end employment and active assignments.",
    ),
    PermissionDefinition(
        "employees.lifecycle.override",
        "Override formal employee lifecycle",
        "Emergency system-administrator-only bypass of formal hiring or termination workflows.",
    ),
    PermissionDefinition(
        "employees.transfer",
        "Transfer employees",
        "Run the transfer business function: move an employee to another staffing slot.",
    ),
    PermissionDefinition(
        "employees.absence.vacation",
        "Register vacations",
        "Run the vacation business function for an employee.",
    ),
    PermissionDefinition(
        "employees.absence.sick_leave",
        "Register sick leaves",
        "Run the sick-leave business function for an employee.",
    ),
    PermissionDefinition(
        "employees.absence.business_trip",
        "Register business trips",
        "Run the business-trip business function for an employee.",
    ),
    PermissionDefinition(
        "employees.absence.day_off",
        "Register days off",
        "Run the day-off business function for an employee.",
    ),
    PermissionDefinition(
        "employees.absence.cancel",
        "Cancel absences",
        "Cancel a scheduled or active employee absence.",
    ),
    PermissionDefinition(
        "delegations.manage", "Manage delegations", "Create and revoke temporary delegations."
    ),
    PermissionDefinition(
        "roles.manage", "Manage roles", "Create roles and maintain role assignments."
    ),
    PermissionDefinition("audit.read", "Read audit history", "View immutable audit events."),
    PermissionDefinition(
        "workflow.definition.read",
        "Read workflow definitions",
        "View process definitions and versions.",
    ),
    PermissionDefinition(
        "workflow.definition.manage",
        "Manage workflow definitions",
        "Create and edit process definition drafts.",
    ),
    PermissionDefinition(
        "workflow.definition.review",
        "Review workflow definitions",
        "Submit or return workflow definition drafts.",
    ),
    PermissionDefinition(
        "workflow.definition.publish",
        "Publish workflow definitions",
        "Publish validated workflow definition versions.",
    ),
    PermissionDefinition(
        "workflow.instance.read",
        "Read workflow instances",
        "View authorized process instances and history.",
    ),
    PermissionDefinition(
        "workflow.task.read", "Read workflow tasks", "View workflow tasks assigned to the actor."
    ),
    PermissionDefinition(
        "workflow.task.act",
        "Act on workflow tasks",
        "Complete, approve, return, or reject assigned workflow tasks.",
    ),
    PermissionDefinition(
        "workflow.task.reassign",
        "Reassign workflow tasks",
        "Reassign tasks through authorized delegation.",
    ),
    PermissionDefinition(
        "documents.read", "Read documents", "View authorized document records and safe metadata."
    ),
    PermissionDefinition(
        "documents.read_sensitive",
        "Read sensitive documents",
        "Read confidential document content.",
    ),
    PermissionDefinition(
        "documents.create", "Create documents", "Create document records and checklist items."
    ),
    PermissionDefinition(
        "documents.upload", "Upload documents", "Upload validated document versions."
    ),
    PermissionDefinition(
        "documents.generate", "Generate documents", "Generate documents from published templates."
    ),
    PermissionDefinition("documents.review", "Review documents", "Approve or reject documents."),
    PermissionDefinition(
        "documents.sign_request",
        "Request document signatures",
        "Request or manually confirm development signatures.",
    ),
    PermissionDefinition(
        "documents.register", "Register documents", "Record controlled document registration."
    ),
    PermissionDefinition(
        "documents.acknowledge", "Acknowledge documents", "Acknowledge assigned document versions."
    ),
    PermissionDefinition(
        "documents.acknowledge_assign",
        "Assign document acknowledgements",
        "Assign immutable document versions for employee acknowledgement.",
    ),
    PermissionDefinition(
        "documents.archive", "Archive documents", "Archive or void authorized documents."
    ),
    PermissionDefinition(
        "recruitment.request.create",
        "Create recruitment requests",
        "Create recruitment requests in authorized units.",
    ),
    PermissionDefinition(
        "recruitment.request.read",
        "Read recruitment requests",
        "Read recruitment requests in scope.",
    ),
    PermissionDefinition(
        "recruitment.request.review_hr",
        "HR recruitment review",
        "Perform HR completeness decisions.",
    ),
    PermissionDefinition(
        "recruitment.request.review_staffing",
        "Staffing recruitment review",
        "Perform staffing and finance decisions.",
    ),
    PermissionDefinition(
        "recruitment.vacancy.manage", "Manage vacancies", "Create and maintain approved vacancies."
    ),
    PermissionDefinition(
        "recruitment.vacancy.publish",
        "Publish vacancies",
        "Record internal and external vacancy publication.",
    ),
    PermissionDefinition(
        "recruitment.candidate.read",
        "Read candidates",
        "Read non-sensitive candidate data in scope.",
    ),
    PermissionDefinition(
        "recruitment.candidate.read_sensitive",
        "Read sensitive candidates",
        "Read protected candidate fields.",
    ),
    PermissionDefinition(
        "recruitment.candidate.manage",
        "Manage candidates",
        "Create and update candidate records and applications.",
    ),
    PermissionDefinition(
        "recruitment.screen", "Screen candidates", "Record candidate screening decisions."
    ),
    PermissionDefinition(
        "recruitment.interview.manage", "Manage interviews", "Schedule interviews and participants."
    ),
    PermissionDefinition(
        "recruitment.interview.evaluate",
        "Evaluate interviews",
        "Submit immutable interview evaluations.",
    ),
    PermissionDefinition(
        "recruitment.commission.manage",
        "Manage commissions",
        "Configure recruitment commission instances.",
    ),
    PermissionDefinition(
        "recruitment.commission.decide",
        "Record commission decisions",
        "Record quorum-backed commission decisions.",
    ),
    PermissionDefinition(
        "recruitment.offer.manage",
        "Manage job offers",
        "Prepare and record candidate offer decisions.",
    ),
    PermissionDefinition(
        "recruitment.hiring.manage",
        "Manage hiring cases",
        "Manage formal hiring and employee conversion.",
    ),
    PermissionDefinition(
        "hiring.request.create",
        "Create hiring requests",
        "Create and edit own new employee hiring requests.",
    ),
    PermissionDefinition(
        "hiring.request.read",
        "Read hiring requests",
        "Read authorized new employee hiring requests.",
    ),
    PermissionDefinition(
        "hiring.request.read_sensitive",
        "Read sensitive hiring data",
        "Read protected candidate data in a hiring request.",
    ),
    PermissionDefinition(
        "hiring.approve.hr_director",
        "HR director hiring approval",
        "Act at the HR document management approval stage.",
    ),
    PermissionDefinition(
        "hiring.approve.economic",
        "Economic planning hiring approval",
        "Act at the economic planning approval stage.",
    ),
    PermissionDefinition(
        "hiring.approve.commission",
        "Commission hiring approval",
        "Act at the competition commission approval stage.",
    ),
    PermissionDefinition(
        "hiring.approve.legal", "Legal hiring approval", "Act at the legal approval stage."
    ),
    PermissionDefinition(
        "hiring.approve.chairman",
        "Chairman hiring approval",
        "Act at the final chairman approval stage.",
    ),
    PermissionDefinition(
        "hiring.request.dispatch",
        "Dispatch approved hiring packages",
        "Send final hiring packages to Accounting and IT.",
    ),
    PermissionDefinition(
        "hiring.request.acknowledge",
        "Acknowledge hiring packages",
        "Acknowledge receipt of an assigned hiring package.",
    ),
    PermissionDefinition(
        "termination.initiate_self",
        "Initiate own termination",
        "Initiate a termination case for the actor.",
    ),
    PermissionDefinition(
        "termination.initiate_unit",
        "Initiate unit termination",
        "Initiate termination in authorized units.",
    ),
    PermissionDefinition(
        "termination.read_self", "Read own termination", "Read the actor's termination case."
    ),
    PermissionDefinition(
        "termination.read_unit",
        "Read unit termination",
        "Read termination cases in authorized units.",
    ),
    PermissionDefinition(
        "termination.read_all", "Read all termination", "Read organization termination cases."
    ),
    PermissionDefinition(
        "termination.review_hr",
        "Review termination as HR",
        "Perform HR completeness and date review.",
    ),
    PermissionDefinition(
        "termination.review_legal",
        "Review termination as legal",
        "Perform configured legal review.",
    ),
    PermissionDefinition(
        "termination.sign", "Sign termination documents", "Act as configured termination signatory."
    ),
    PermissionDefinition(
        "termination.handover", "Confirm handover", "Complete manager handover tasks."
    ),
    PermissionDefinition(
        "termination.assets.confirm", "Confirm asset return", "Complete asset return tasks."
    ),
    PermissionDefinition(
        "termination.access.confirm",
        "Confirm access revocation",
        "Complete IT access-revocation tasks.",
    ),
    PermissionDefinition(
        "termination.settlement.confirm",
        "Confirm settlement",
        "Complete accounting settlement tasks.",
    ),
    PermissionDefinition(
        "termination.exit_interview.manage",
        "Manage exit interviews",
        "Complete restricted exit-interview tasks.",
    ),
    PermissionDefinition(
        "termination.complete",
        "Complete termination",
        "Finalize an effective and fully offboarded termination case.",
    ),
    PermissionDefinition("absence.read_self", "Read own absences", "Read own leave and trips."),
    PermissionDefinition("absence.read_unit", "Read unit absences", "Read unit leave and trips."),
    PermissionDefinition("absence.read_all", "Read all absences", "Read organization absences."),
    PermissionDefinition("leave.request", "Request leave", "Submit and correct own leave."),
    PermissionDefinition("leave.review_manager", "Review unit leave", "Review leave as manager."),
    PermissionDefinition("leave.review_hr", "Review leave as HR", "Finalize leave decisions."),
    PermissionDefinition("leave.balance.manage", "Manage leave balances", "Adjust entitlements."),
    PermissionDefinition("business_trip.request", "Request trip", "Submit and correct own trips."),
    PermissionDefinition(
        "business_trip.review_manager", "Review unit trips", "Review trips as manager."
    ),
    PermissionDefinition(
        "business_trip.review_finance", "Review trip finance", "Approve trip funding."
    ),
    PermissionDefinition(
        "business_trip.register", "Register business trips", "Complete HR trip registration."
    ),
    PermissionDefinition(
        "regulated_hiring.read",
        "Read regulated hiring",
        "Read the normative hiring catalog, cases, stages, and safe history.",
    ),
    PermissionDefinition(
        "regulated_hiring.start",
        "Start regulated hiring",
        "Start hiring only for an approved request and a confirmed staffing slot.",
    ),
    PermissionDefinition(
        "regulated_hiring.stage.act",
        "Act on regulated hiring stages",
        "Complete, return, reject, or cancel a stage when holding its functional role.",
    ),
    PermissionDefinition(
        "regulated_hiring.form.manage",
        "Manage regulated hiring forms",
        "Create, sign, and supersede NAIM-01 through NAIM-21 records.",
    ),
    PermissionDefinition(
        "regulated_hiring.authority.manage",
        "Manage normative authority",
        "Maintain confirmed, model, and document-required authority bindings.",
    ),
)

REQUIRED_PERMISSION_CODES: frozenset[str] = frozenset(item.code for item in PERMISSION_CATALOG)
