import { ApiClient } from '../../../repositories/apiRepositories';
import type { PersonaId } from '../../../shared/types';
import type { AddEmployeeFormValues } from '../add-employee/schema';

export const DEMO_ORGANIZATION_ID = '63f3d186-4702-561f-b6f3-c410df730708';

export type HiringAttachment = { id: string; category: 'identity' | 'diploma'; documentId: string; versionId: string; originalFilename: string; sizeBytes: number; mimeType: string };
export type HiringRequest = {
  id: string; organizationId: string; requestNumber: string; candidateName: string; initiatorName: string;
  status: string; currentStage?: number; currentStageCode?: string; currentStageName?: string; revision: number;
  personal: Record<string, unknown>; employmentData: Record<string, unknown>; educationData: Record<string, unknown>;
  pdfVersionId?: string; finalPdfVersionId?: string; attachments: HiringAttachment[];
  dispatches: Array<{ id: string; recipientType: 'accounting' | 'it'; status: string; acknowledgedAt?: string }>;
  hiredEmployee?: { id: string; employeeNumber: string; corporateEmail?: string } | null;
  createdAt: string; submittedAt?: string; finalApprovedAt?: string;
};

const api = new ApiClient();

const personaToHiringDevUser: Record<string, string> = {
  executive: 'chairman',
  'hr-specialist': 'hr.initiator',
  'hr-initiator': 'hr.initiator',
  'hr-director': 'hr.director',
  'economic-director': 'economic.director',
  'commission-reviewer': 'commission',
  'legal-reviewer': 'legal',
  'board-chairman': 'chairman',
  accountant: 'accountant',
  'it-specialist': 'it.specialist'
};

export type HiringRequestScope = 'mine' | 'inbox' | 'received' | 'dispatch' | undefined;

export const hiringStatusLabels: Record<string, string> = {
  draft: 'Черновик', pdf_generated: 'PDF готов', under_review: 'На согласовании',
  returned: 'Возвращено', rejected: 'Отклонено', final_approved: 'Финально согласовано',
  dispatched: 'Отправлено', partially_acknowledged: 'Получено частично', completed: 'Завершено'
};

const personaApprovalStage: Partial<Record<PersonaId, string>> = {
  executive: 'chairman',
  'hr-director': 'hr_director',
  'economic-director': 'economic_director',
  'commission-reviewer': 'competition_commission',
  'legal-reviewer': 'legal_department',
  'board-chairman': 'chairman'
};

const personaDispatchRecipient: Partial<Record<PersonaId, 'accounting' | 'it'>> = {
  accountant: 'accounting',
  'it-specialist': 'it'
};

export function canPersonaApproveRequest(persona: PersonaId, request: HiringRequest) {
  return request.status === 'under_review' && personaApprovalStage[persona] === request.currentStageCode;
}

export function canPersonaAcknowledgeRequest(persona: PersonaId, request: HiringRequest) {
  const recipient = personaDispatchRecipient[persona];
  return Boolean(recipient && ['dispatched', 'partially_acknowledged'].includes(request.status)
    && request.dispatches.some((dispatch) => dispatch.recipientType === recipient && dispatch.status !== 'acknowledged'));
}

function hiringDevUser() {
  try {
    const stored = JSON.parse(localStorage.getItem('ertis-developer-settings') ?? '{}') as { state?: { persona?: string } };
    return personaToHiringDevUser[stored.state?.persona ?? ''] ?? 'hr.initiator';
  } catch {
    return 'hr.initiator';
  }
}

function payload(values: AddEmployeeFormValues) {
  return {
    organizationId: DEMO_ORGANIZATION_ID,
    personal: {
      lastName: values.lastName, firstName: values.firstName, middleName: values.middleName,
      iin: values.iin, birthDate: values.birthDate, gender: values.gender, citizenship: values.citizenship,
      maritalStatus: values.maritalStatus, personalPhone: values.personalPhone, personalEmail: values.personalEmail,
      address: values.address, identityDocumentType: values.identityDocumentType,
      identityDocumentNumber: values.identityDocumentNumber, identityIssueDate: values.identityIssueDate,
      identityExpirationDate: values.identityExpirationDate, issuingAuthority: values.issuingAuthority,
      emergencyContact: values.emergencyContact, emergencyPhone: values.emergencyPhone
    },
    employment: {
      department: values.department, position: values.position, employmentType: values.employmentType,
      workArrangement: values.workArrangement, workplace: values.workplace, startDate: values.startDate,
      probationMonths: values.probationMonths, schedule: values.schedule, hiringReason: values.hiringReason,
      team: values.team, manager: values.manager, fte: values.fte, salary: values.salary,
      currency: values.currency, responsibilities: values.responsibilities, justification: values.justification,
      recipient: values.recipient, recipientPosition: values.recipientPosition,
      recipientDepartment: values.recipientDepartment, recipientType: values.recipientType,
      requestDate: values.requestDate, initiatorName: values.initiatorName,
      initiatorPosition: values.initiatorPosition, initiatorDepartment: values.initiatorDepartment,
      initiatorEmail: values.initiatorEmail, initiatorPhone: values.initiatorPhone,
      requestText: values.requestText
    },
    education: {
      educationLevel: values.educationLevel, institution: values.institution,
      specialization: values.specialization, totalExperience: values.totalExperience,
      graduationYear: values.graduationYear, qualification: values.qualification,
      relevantExperience: values.relevantExperience, skills: values.skills,
      languages: values.languages, certifications: values.certifications,
      additionalInfo: values.additionalInfo
    }
  };
}

export const hiringRequestsApi = {
  create: (values: AddEmployeeFormValues) => api.post<HiringRequest>('/hiring-requests', payload(values), hiringDevUser()),
  update: (id: string, revision: number, values: AddEmployeeFormValues) => api.patch<HiringRequest>(`/hiring-requests/${id}`, { ...payload(values), revision }, hiringDevUser()),
  list: async (scope: HiringRequestScope = 'mine') => {
    const requests = await api.get<HiringRequest[]>(`/hiring-requests?organizationId=${DEMO_ORGANIZATION_ID}${scope ? `&scope=${scope}` : ''}`, hiringDevUser());
    return scope === 'dispatch' ? requests.filter((request) => request.status === 'final_approved') : requests;
  },
  get: (id: string) => api.get<HiringRequest>(`/hiring-requests/${id}?organizationId=${DEMO_ORGANIZATION_ID}`, hiringDevUser()),
  upload: (id: string, category: 'identity' | 'diploma', file: File) => {
    const data = new FormData(); data.append('organizationId', DEMO_ORGANIZATION_ID); data.append('category', category); data.append('file', file);
    return api.upload<Record<string, unknown>>(`/hiring-requests/${id}/attachments`, data, hiringDevUser());
  },
  generatePdf: (id: string, revision: number) => api.post<Record<string, unknown>>(`/hiring-requests/${id}/generate-pdf`, { organizationId: DEMO_ORGANIZATION_ID, revision }, hiringDevUser()),
  submit: (id: string, revision: number) => api.post<HiringRequest>(`/hiring-requests/${id}/submit`, { organizationId: DEMO_ORGANIZATION_ID, revision }, hiringDevUser()),
  decide: (id: string, revision: number, decision: 'approve' | 'return' | 'reject', comment: string) => api.post<HiringRequest>(`/hiring-requests/${id}/decision`, { organizationId: DEMO_ORGANIZATION_ID, revision, decision, comment }, hiringDevUser()),
  dispatch: (id: string, revision: number) => api.post<HiringRequest>(`/hiring-requests/${id}/dispatch`, { organizationId: DEMO_ORGANIZATION_ID, revision }, hiringDevUser()),
  acknowledge: (id: string, revision: number, comment = '') => api.post<HiringRequest>(`/hiring-requests/${id}/acknowledge`, { organizationId: DEMO_ORGANIZATION_ID, revision, comment }, hiringDevUser()),
  downloadUrl: (id: string, versionId: string, inline = false) => `/api/v1/hiring-requests/${id}/documents/${versionId}/download?organizationId=${DEMO_ORGANIZATION_ID}${inline ? '&inline=true' : ''}`
};
