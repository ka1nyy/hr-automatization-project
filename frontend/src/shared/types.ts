export type Locale = 'ru' | 'kk' | 'en';
export type ThemeMode = 'light' | 'dark' | 'system';
export type PersonaId = 'secretary' | 'executive' | 'employee' | 'hr-specialist' | 'process-designer';
export type Priority = 'normal' | 'high' | 'urgent';
export type CorrespondenceStatus =
  | 'draft'
  | 'registered'
  | 'resolution'
  | 'execution'
  | 'approval'
  | 'signature'
  | 'dispatch'
  | 'completed';

export interface Attachment {
  id: string;
  name: string;
  size: string;
  kind: 'scan' | 'attachment' | 'response';
}

export interface AuditEvent {
  id: string;
  at: string;
  actor: string;
  action: string;
  detail: string;
}

export interface Correspondence {
  id: string;
  number: string;
  sender: string;
  senderNumber: string;
  senderDate: string;
  receivedAt: string;
  subject: string;
  summary: string;
  documentType: string;
  channel: string;
  department: string;
  executive: string;
  executor: string;
  dueDate: string;
  priority: Priority;
  status: CorrespondenceStatus;
  workflowStep: string;
  confidentiality: 'public' | 'internal' | 'restricted';
  responseRequired: boolean;
  attachments: Attachment[];
  tags: string[];
  audit: AuditEvent[];
}

export interface IncomingLetterInput {
  sender: string;
  senderType: string;
  senderNumber: string;
  senderDate: string;
  channel: string;
  documentType: string;
  subject: string;
  summary: string;
  language: string;
  pageCount: number;
  confidentiality: Correspondence['confidentiality'];
  priority: Priority;
  responseRequired: boolean;
  dueDate: string;
  department: string;
  executive: string;
  notes: string;
}

export interface WorkTask {
  id: string;
  title: string;
  documentNumber: string;
  process: string;
  role: string;
  department: string;
  dueDate: string;
  priority: Priority;
  state: 'available' | 'claimed' | 'completed' | 'overdue';
  assignee?: string;
}

export interface ProcessDefinition {
  id: string;
  name: string;
  version: number;
  state: 'published' | 'draft' | 'incident';
  activeInstances: number;
  owner: string;
  updatedAt: string;
  steps: string[];
}

export interface Employee {
  id: string;
  name: string;
  initials: string;
  role: string;
  department: string;
  candidateGroups: string[];
  status: 'active' | 'acting' | 'delegated';
}

export interface DashboardSnapshot {
  incomingToday: number;
  awaitingResolution: number;
  activeTasks: number;
  overdue: number;
  signatureQueue: number;
  dispatchQueue: number;
}
