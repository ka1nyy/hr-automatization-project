"""Stable permission identifiers exposed by Module 1.

Every permission the source tree checks is declared here once, as a named constant, and
the catalogue is derived from those constants.  Use the constants rather than string
literals: a typo becomes an import error instead of a permission check that silently
never passes.

    from app.modules.access_control.domain.permissions import Permissions

    await authorize(principal, Permissions.EMPLOYEES_READ, organization_id)

Adding a constant here makes the permission a *system* permission: the seed marks it as
one, and administrators may reword but not delete it.  Administrator-defined permissions
live only in the database and never appear in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class PermissionDefinition:
    code: str
    name: str
    description: str

    def __str__(self) -> str:
        """Allow a definition to be passed anywhere a permission code is expected."""

        return self.code


class Permissions:
    """Named handles for every permission the source tree checks by code."""

    ORGANIZATION_READ: Final = PermissionDefinition(
        'organization.read',
        'Read organization',
        'View organization details.',
    )
    ORGANIZATION_STRUCTURE_READ: Final = PermissionDefinition(
        'organization.structure.read',
        'Read organization structures',
        'View current and historical structures.',
    )
    ORGANIZATION_STRUCTURE_DRAFT_CREATE: Final = PermissionDefinition(
        'organization.structure.draft.create',
        'Create structure drafts',
        'Create a draft structure version.',
    )
    ORGANIZATION_STRUCTURE_EDIT: Final = PermissionDefinition(
        'organization.structure.edit',
        'Edit structure drafts',
        'Edit an organization structure draft.',
    )
    ORGANIZATION_STRUCTURE_REVIEW: Final = PermissionDefinition(
        'organization.structure.review',
        'Review structure drafts',
        'Submit, approve, or return a draft.',
    )
    ORGANIZATION_STRUCTURE_PUBLISH: Final = PermissionDefinition(
        'organization.structure.publish',
        'Publish structures',
        'Publish a validated structure version.',
    )
    ORGANIZATION_UNIT_MANAGE: Final = PermissionDefinition(
        'organization.unit.manage',
        'Manage units',
        'Create, edit, move, and deactivate units.',
    )
    ORGANIZATION_RELATIONSHIP_MANAGE: Final = PermissionDefinition(
        'organization.relationship.manage',
        'Manage relationships',
        'Maintain additional organization relationships.',
    )
    ORGANIZATION_STAFFING_MANAGE: Final = PermissionDefinition(
        'organization.staffing.manage',
        'Manage staffing',
        'Create, edit, and close staffing slots.',
    )
    EMPLOYEES_READ: Final = PermissionDefinition(
        'employees.read',
        'Read employees',
        'View non-sensitive employee data.',
    )
    EMPLOYEES_READ_SENSITIVE: Final = PermissionDefinition(
        'employees.read_sensitive',
        'Read sensitive employee data',
        'View explicitly protected employee fields.',
    )
    EMPLOYEES_CREATE: Final = PermissionDefinition(
        'employees.create',
        'Create employees',
        'Create employee draft records.',
    )
    EMPLOYEES_EDIT: Final = PermissionDefinition(
        'employees.edit',
        'Edit employees',
        'Edit employee records.',
    )
    EMPLOYEES_ASSIGN: Final = PermissionDefinition(
        'employees.assign',
        'Assign employees',
        'Create and end employee assignments.',
    )
    EMPLOYEES_HIRE: Final = PermissionDefinition(
        'employees.hire',
        'Hire employees',
        'Run the hire business function: create an employment record with an assignment.',
    )
    EMPLOYEES_TERMINATE: Final = PermissionDefinition(
        'employees.terminate',
        'Terminate employees',
        'Run the terminate business function: end employment and active assignments.',
    )
    EMPLOYEES_LIFECYCLE_OVERRIDE: Final = PermissionDefinition(
        'employees.lifecycle.override',
        'Override formal employee lifecycle',
        'Emergency system-administrator-only bypass of formal hiring or termination workflows.',
    )
    EMPLOYEES_TRANSFER: Final = PermissionDefinition(
        'employees.transfer',
        'Transfer employees',
        'Run the transfer business function: move an employee to another staffing slot.',
    )
    EMPLOYEES_ABSENCE_VACATION: Final = PermissionDefinition(
        'employees.absence.vacation',
        'Register vacations',
        'Run the vacation business function for an employee.',
    )
    EMPLOYEES_ABSENCE_SICK_LEAVE: Final = PermissionDefinition(
        'employees.absence.sick_leave',
        'Register sick leaves',
        'Run the sick-leave business function for an employee.',
    )
    EMPLOYEES_ABSENCE_BUSINESS_TRIP: Final = PermissionDefinition(
        'employees.absence.business_trip',
        'Register business trips',
        'Run the business-trip business function for an employee.',
    )
    EMPLOYEES_ABSENCE_DAY_OFF: Final = PermissionDefinition(
        'employees.absence.day_off',
        'Register days off',
        'Run the day-off business function for an employee.',
    )
    EMPLOYEES_ABSENCE_CANCEL: Final = PermissionDefinition(
        'employees.absence.cancel',
        'Cancel absences',
        'Cancel a scheduled or active employee absence.',
    )
    DELEGATIONS_MANAGE: Final = PermissionDefinition(
        'delegations.manage',
        'Manage delegations',
        'Create and revoke temporary delegations.',
    )
    ROLES_MANAGE: Final = PermissionDefinition(
        'roles.manage',
        'Manage roles',
        'Create roles and maintain role assignments.',
    )
    AUDIT_READ: Final = PermissionDefinition(
        'audit.read',
        'Read audit history',
        'View immutable audit events.',
    )
    WORKFLOW_DEFINITION_READ: Final = PermissionDefinition(
        'workflow.definition.read',
        'Read workflow definitions',
        'View process definitions and versions.',
    )
    WORKFLOW_DEFINITION_MANAGE: Final = PermissionDefinition(
        'workflow.definition.manage',
        'Manage workflow definitions',
        'Create and edit process definition drafts.',
    )
    WORKFLOW_DEFINITION_REVIEW: Final = PermissionDefinition(
        'workflow.definition.review',
        'Review workflow definitions',
        'Submit or return workflow definition drafts.',
    )
    WORKFLOW_DEFINITION_PUBLISH: Final = PermissionDefinition(
        'workflow.definition.publish',
        'Publish workflow definitions',
        'Publish validated workflow definition versions.',
    )
    WORKFLOW_INSTANCE_READ: Final = PermissionDefinition(
        'workflow.instance.read',
        'Read workflow instances',
        'View authorized process instances and history.',
    )
    WORKFLOW_TASK_READ: Final = PermissionDefinition(
        'workflow.task.read',
        'Read workflow tasks',
        'View workflow tasks assigned to the actor.',
    )
    WORKFLOW_TASK_ACT: Final = PermissionDefinition(
        'workflow.task.act',
        'Act on workflow tasks',
        'Complete, approve, return, or reject assigned workflow tasks.',
    )
    WORKFLOW_TASK_REASSIGN: Final = PermissionDefinition(
        'workflow.task.reassign',
        'Reassign workflow tasks',
        'Reassign tasks through authorized delegation.',
    )
    DOCUMENTS_READ: Final = PermissionDefinition(
        'documents.read',
        'Read documents',
        'View authorized document records and safe metadata.',
    )
    DOCUMENTS_READ_SENSITIVE: Final = PermissionDefinition(
        'documents.read_sensitive',
        'Read sensitive documents',
        'Read confidential document content.',
    )
    DOCUMENTS_CREATE: Final = PermissionDefinition(
        'documents.create',
        'Create documents',
        'Create document records and checklist items.',
    )
    DOCUMENTS_UPLOAD: Final = PermissionDefinition(
        'documents.upload',
        'Upload documents',
        'Upload validated document versions.',
    )
    DOCUMENTS_GENERATE: Final = PermissionDefinition(
        'documents.generate',
        'Generate documents',
        'Generate documents from published templates.',
    )
    DOCUMENTS_REVIEW: Final = PermissionDefinition(
        'documents.review',
        'Review documents',
        'Approve or reject documents.',
    )
    DOCUMENTS_SIGN_REQUEST: Final = PermissionDefinition(
        'documents.sign_request',
        'Request document signatures',
        'Request or manually confirm development signatures.',
    )
    DOCUMENTS_REGISTER: Final = PermissionDefinition(
        'documents.register',
        'Register documents',
        'Record controlled document registration.',
    )
    DOCUMENTS_ACKNOWLEDGE: Final = PermissionDefinition(
        'documents.acknowledge',
        'Acknowledge documents',
        'Acknowledge assigned document versions.',
    )
    DOCUMENTS_ACKNOWLEDGE_ASSIGN: Final = PermissionDefinition(
        'documents.acknowledge_assign',
        'Assign document acknowledgements',
        'Assign immutable document versions for employee acknowledgement.',
    )
    DOCUMENTS_ARCHIVE: Final = PermissionDefinition(
        'documents.archive',
        'Archive documents',
        'Archive or void authorized documents.',
    )
    RECRUITMENT_REQUEST_CREATE: Final = PermissionDefinition(
        'recruitment.request.create',
        'Create recruitment requests',
        'Create recruitment requests in authorized units.',
    )
    RECRUITMENT_REQUEST_READ: Final = PermissionDefinition(
        'recruitment.request.read',
        'Read recruitment requests',
        'Read recruitment requests in scope.',
    )
    RECRUITMENT_REQUEST_REVIEW_HR: Final = PermissionDefinition(
        'recruitment.request.review_hr',
        'HR recruitment review',
        'Perform HR completeness decisions.',
    )
    RECRUITMENT_REQUEST_REVIEW_STAFFING: Final = PermissionDefinition(
        'recruitment.request.review_staffing',
        'Staffing recruitment review',
        'Perform staffing and finance decisions.',
    )
    RECRUITMENT_VACANCY_MANAGE: Final = PermissionDefinition(
        'recruitment.vacancy.manage',
        'Manage vacancies',
        'Create and maintain approved vacancies.',
    )
    RECRUITMENT_VACANCY_PUBLISH: Final = PermissionDefinition(
        'recruitment.vacancy.publish',
        'Publish vacancies',
        'Record internal and external vacancy publication.',
    )
    RECRUITMENT_CANDIDATE_READ: Final = PermissionDefinition(
        'recruitment.candidate.read',
        'Read candidates',
        'Read non-sensitive candidate data in scope.',
    )
    RECRUITMENT_CANDIDATE_READ_SENSITIVE: Final = PermissionDefinition(
        'recruitment.candidate.read_sensitive',
        'Read sensitive candidates',
        'Read protected candidate fields.',
    )
    RECRUITMENT_CANDIDATE_MANAGE: Final = PermissionDefinition(
        'recruitment.candidate.manage',
        'Manage candidates',
        'Create and update candidate records and applications.',
    )
    RECRUITMENT_SCREEN: Final = PermissionDefinition(
        'recruitment.screen',
        'Screen candidates',
        'Record candidate screening decisions.',
    )
    RECRUITMENT_INTERVIEW_MANAGE: Final = PermissionDefinition(
        'recruitment.interview.manage',
        'Manage interviews',
        'Schedule interviews and participants.',
    )
    RECRUITMENT_INTERVIEW_EVALUATE: Final = PermissionDefinition(
        'recruitment.interview.evaluate',
        'Evaluate interviews',
        'Submit immutable interview evaluations.',
    )
    RECRUITMENT_COMMISSION_MANAGE: Final = PermissionDefinition(
        'recruitment.commission.manage',
        'Manage commissions',
        'Configure recruitment commission instances.',
    )
    RECRUITMENT_COMMISSION_DECIDE: Final = PermissionDefinition(
        'recruitment.commission.decide',
        'Record commission decisions',
        'Record quorum-backed commission decisions.',
    )
    RECRUITMENT_OFFER_MANAGE: Final = PermissionDefinition(
        'recruitment.offer.manage',
        'Manage job offers',
        'Prepare and record candidate offer decisions.',
    )
    RECRUITMENT_HIRING_MANAGE: Final = PermissionDefinition(
        'recruitment.hiring.manage',
        'Manage hiring cases',
        'Manage formal hiring and employee conversion.',
    )
    HIRING_REQUEST_CREATE: Final = PermissionDefinition(
        'hiring.request.create',
        'Create hiring requests',
        'Create and edit own new employee hiring requests.',
    )
    HIRING_REQUEST_READ: Final = PermissionDefinition(
        'hiring.request.read',
        'Read hiring requests',
        'Read authorized new employee hiring requests.',
    )
    HIRING_REQUEST_READ_SENSITIVE: Final = PermissionDefinition(
        'hiring.request.read_sensitive',
        'Read sensitive hiring data',
        'Read protected candidate data in a hiring request.',
    )
    HIRING_APPROVE_HR_DIRECTOR: Final = PermissionDefinition(
        'hiring.approve.hr_director',
        'HR director hiring approval',
        'Act at the HR document management approval stage.',
    )
    HIRING_APPROVE_ECONOMIC: Final = PermissionDefinition(
        'hiring.approve.economic',
        'Economic planning hiring approval',
        'Act at the economic planning approval stage.',
    )
    HIRING_APPROVE_COMMISSION: Final = PermissionDefinition(
        'hiring.approve.commission',
        'Commission hiring approval',
        'Act at the competition commission approval stage.',
    )
    HIRING_APPROVE_LEGAL: Final = PermissionDefinition(
        'hiring.approve.legal',
        'Legal hiring approval',
        'Act at the legal approval stage.',
    )
    HIRING_APPROVE_CHAIRMAN: Final = PermissionDefinition(
        'hiring.approve.chairman',
        'Chairman hiring approval',
        'Act at the final chairman approval stage.',
    )
    HIRING_REQUEST_DISPATCH: Final = PermissionDefinition(
        'hiring.request.dispatch',
        'Dispatch approved hiring packages',
        'Send final hiring packages to Accounting and IT.',
    )
    HIRING_REQUEST_ACKNOWLEDGE: Final = PermissionDefinition(
        'hiring.request.acknowledge',
        'Acknowledge hiring packages',
        'Acknowledge receipt of an assigned hiring package.',
    )
    TERMINATION_INITIATE_SELF: Final = PermissionDefinition(
        'termination.initiate_self',
        'Initiate own termination',
        'Initiate a termination case for the actor.',
    )
    TERMINATION_INITIATE_UNIT: Final = PermissionDefinition(
        'termination.initiate_unit',
        'Initiate unit termination',
        'Initiate termination in authorized units.',
    )
    TERMINATION_READ_SELF: Final = PermissionDefinition(
        'termination.read_self',
        'Read own termination',
        "Read the actor's termination case.",
    )
    TERMINATION_READ_UNIT: Final = PermissionDefinition(
        'termination.read_unit',
        'Read unit termination',
        'Read termination cases in authorized units.',
    )
    TERMINATION_READ_ALL: Final = PermissionDefinition(
        'termination.read_all',
        'Read all termination',
        'Read organization termination cases.',
    )
    TERMINATION_REVIEW_HR: Final = PermissionDefinition(
        'termination.review_hr',
        'Review termination as HR',
        'Perform HR completeness and date review.',
    )
    TERMINATION_REVIEW_LEGAL: Final = PermissionDefinition(
        'termination.review_legal',
        'Review termination as legal',
        'Perform configured legal review.',
    )
    TERMINATION_SIGN: Final = PermissionDefinition(
        'termination.sign',
        'Sign termination documents',
        'Act as configured termination signatory.',
    )
    TERMINATION_HANDOVER: Final = PermissionDefinition(
        'termination.handover',
        'Confirm handover',
        'Complete manager handover tasks.',
    )
    TERMINATION_ASSETS_CONFIRM: Final = PermissionDefinition(
        'termination.assets.confirm',
        'Confirm asset return',
        'Complete asset return tasks.',
    )
    TERMINATION_ACCESS_CONFIRM: Final = PermissionDefinition(
        'termination.access.confirm',
        'Confirm access revocation',
        'Complete IT access-revocation tasks.',
    )
    TERMINATION_SETTLEMENT_CONFIRM: Final = PermissionDefinition(
        'termination.settlement.confirm',
        'Confirm settlement',
        'Complete accounting settlement tasks.',
    )
    TERMINATION_EXIT_INTERVIEW_MANAGE: Final = PermissionDefinition(
        'termination.exit_interview.manage',
        'Manage exit interviews',
        'Complete restricted exit-interview tasks.',
    )
    TERMINATION_COMPLETE: Final = PermissionDefinition(
        'termination.complete',
        'Complete termination',
        'Finalize an effective and fully offboarded termination case.',
    )
    ABSENCE_READ_SELF: Final = PermissionDefinition(
        'absence.read_self',
        'Read own absences',
        'Read own leave and trips.',
    )
    ABSENCE_READ_UNIT: Final = PermissionDefinition(
        'absence.read_unit',
        'Read unit absences',
        'Read unit leave and trips.',
    )
    ABSENCE_READ_ALL: Final = PermissionDefinition(
        'absence.read_all',
        'Read all absences',
        'Read organization absences.',
    )
    LEAVE_REQUEST: Final = PermissionDefinition(
        'leave.request',
        'Request leave',
        'Submit and correct own leave.',
    )
    LEAVE_REVIEW_MANAGER: Final = PermissionDefinition(
        'leave.review_manager',
        'Review unit leave',
        'Review leave as manager.',
    )
    LEAVE_REVIEW_HR: Final = PermissionDefinition(
        'leave.review_hr',
        'Review leave as HR',
        'Finalize leave decisions.',
    )
    LEAVE_BALANCE_MANAGE: Final = PermissionDefinition(
        'leave.balance.manage',
        'Manage leave balances',
        'Adjust entitlements.',
    )
    BUSINESS_TRIP_REQUEST: Final = PermissionDefinition(
        'business_trip.request',
        'Request trip',
        'Submit and correct own trips.',
    )
    BUSINESS_TRIP_REVIEW_MANAGER: Final = PermissionDefinition(
        'business_trip.review_manager',
        'Review unit trips',
        'Review trips as manager.',
    )
    BUSINESS_TRIP_REVIEW_FINANCE: Final = PermissionDefinition(
        'business_trip.review_finance',
        'Review trip finance',
        'Approve trip funding.',
    )
    BUSINESS_TRIP_REGISTER: Final = PermissionDefinition(
        'business_trip.register',
        'Register business trips',
        'Complete HR trip registration.',
    )


PERMISSION_CATALOG: tuple[PermissionDefinition, ...] = tuple(
    value
    for value in vars(Permissions).values()
    if isinstance(value, PermissionDefinition)
)

REQUIRED_PERMISSION_CODES: frozenset[str] = frozenset(item.code for item in PERMISSION_CATALOG)
