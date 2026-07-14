export type HrEmployeeStatus = 'active' | 'probation' | 'on_leave' | 'sick_leave';
export type Availability = 'available' | 'away' | 'remote';
export type LeaveRequestStatus = 'pending_manager' | 'hr_review' | 'approved' | 'rejected';

export interface HrAuditEvent {
  id: string;
  at: string;
  actor: string;
  action: string;
  detail: string;
}

export interface HrEmployee {
  id: string;
  employeeNumber: string;
  fullName: string;
  initials: string;
  position: string;
  department: string;
  manager: string | null;
  workEmail: string;
  phone: string;
  startDate: string;
  location: string;
  status: HrEmployeeStatus;
  availability: Availability;
  employmentType: string;
  contractEnd: string | null;
  probationEnd: string | null;
  leaveBalance: number;
  personnelFileCompleteness: number;
  salary: number;
  currency: 'KZT';
  candidateGroups: string[];
  skills: string[];
}

export interface LeaveRequest {
  id: string;
  employeeId: string;
  employeeName: string;
  leaveType: string;
  startDate: string;
  endDate: string;
  days: number;
  comment: string;
  substitute: string;
  status: LeaveRequestStatus;
  documentNumber: string;
  workflowStep: string;
  createdAt: string;
  audit: HrAuditEvent[];
}

export interface CreateLeaveRequestInput {
  employeeId: string;
  leaveType: string;
  startDate: string;
  endDate: string;
  comment: string;
  substitute: string;
}

export interface HrOverview {
  activeEmployees: number;
  onProbation: number;
  onLeave: number;
  openVacancies: number;
  onboardingCases: number;
  overdueTasks: number;
  incompleteFiles: number;
  expiringContracts: number;
}
