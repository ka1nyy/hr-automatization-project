import { ApiClient } from '../../../repositories/apiRepositories';
import type { AddEmployeeFormValues } from '../add-employee/schema';

export const DEMO_ORGANIZATION_ID = '63f3d186-4702-561f-b6f3-c410df730708';

export type HiringAttachment = { id: string; category: 'identity' | 'diploma'; documentId: string; versionId: string; originalFilename: string; sizeBytes: number; mimeType: string };
export type ApprovalDecision = { id: string; stageNumber: number; stageCode: string; stageName: string; approverName: string; approverRole: string; decision: 'approve' | 'return' | 'reject'; comment?: string; decidedAt: string };
export type HiringRequest = {
  id: string; organizationId: string; requestNumber: string; candidateName: string; initiatorName: string;
  status: string; currentStage?: number; currentStageCode?: string; currentStageName?: string; revision: number;
  personal: Record<string, unknown>; employmentData: Record<string, unknown>; educationData: Record<string, unknown>;
  pdfVersionId?: string; finalPdfVersionId?: string; attachments: HiringAttachment[]; decisions: ApprovalDecision[];
  approvalStages: Array<{ stageNumber: number; code: string; name: string; role: string }>;
  dispatches: Array<{ id: string; recipientType: 'accounting' | 'it'; status: string; acknowledgedAt?: string }>;
  createdAt: string; submittedAt?: string; finalApprovedAt?: string;
};

const api = new ApiClient();

function payload(values: AddEmployeeFormValues) {
  return {
    organizationId: DEMO_ORGANIZATION_ID,
    personal: {
      lastName: values.lastName, firstName: values.firstName, middleName: values.middleName,
      iin: values.iin, birthDate: values.birthDate, gender: values.gender, citizenship: values.citizenship,
      maritalStatus: values.maritalStatus, personalPhone: values.personalPhone, personalEmail: values.personalEmail,
      address: values.address, identityDocumentType: values.identityDocumentType,
      identityDocumentNumber: values.identityDocumentNumber
    },
    employment: {
      department: values.department, position: values.position, employmentType: values.employmentType,
      workArrangement: values.workArrangement, workplace: values.workplace, startDate: values.startDate,
      probationMonths: values.probationMonths, schedule: values.schedule, hiringReason: values.hiringReason
    },
    education: {
      educationLevel: values.educationLevel, institution: values.institution,
      specialization: values.specialization, totalExperience: values.totalExperience
    }
  };
}

export const hiringRequestsApi = {
  create: (values: AddEmployeeFormValues) => api.post<HiringRequest>('/hiring-requests', payload(values)),
  update: (id: string, revision: number, values: AddEmployeeFormValues) => api.patch<HiringRequest>(`/hiring-requests/${id}`, { ...payload(values), revision }),
  list: (scope = 'mine') => api.get<HiringRequest[]>(`/hiring-requests?organizationId=${DEMO_ORGANIZATION_ID}&scope=${scope}`),
  get: (id: string) => api.get<HiringRequest>(`/hiring-requests/${id}?organizationId=${DEMO_ORGANIZATION_ID}`),
  upload: (id: string, category: 'identity' | 'diploma', file: File) => {
    const data = new FormData(); data.append('organizationId', DEMO_ORGANIZATION_ID); data.append('category', category); data.append('file', file);
    return api.upload<Record<string, unknown>>(`/hiring-requests/${id}/attachments`, data);
  },
  generatePdf: (id: string, revision: number) => api.post<Record<string, unknown>>(`/hiring-requests/${id}/generate-pdf`, { organizationId: DEMO_ORGANIZATION_ID, revision }),
  submit: (id: string, revision: number) => api.post<HiringRequest>(`/hiring-requests/${id}/submit`, { organizationId: DEMO_ORGANIZATION_ID, revision }),
  decide: (id: string, revision: number, decision: 'approve' | 'return' | 'reject', comment: string) => api.post<HiringRequest>(`/hiring-requests/${id}/decision`, { organizationId: DEMO_ORGANIZATION_ID, revision, decision, comment }),
  dispatch: (id: string, revision: number) => api.post<HiringRequest>(`/hiring-requests/${id}/dispatch`, { organizationId: DEMO_ORGANIZATION_ID, revision }),
  acknowledge: (id: string, revision: number, comment = '') => api.post<HiringRequest>(`/hiring-requests/${id}/acknowledge`, { organizationId: DEMO_ORGANIZATION_ID, revision, comment }),
  downloadUrl: (id: string, versionId: string, inline = false) => `/api/v1/hiring-requests/${id}/documents/${versionId}/download?organizationId=${DEMO_ORGANIZATION_ID}${inline ? '&inline=true' : ''}`
};
