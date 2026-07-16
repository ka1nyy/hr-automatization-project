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

export type AbsenceTypeKey = 'vacation' | 'sick_leave' | 'business_trip' | 'day_off';
export type AbsenceStatusKey = 'scheduled' | 'active' | 'completed' | 'cancelled';

export interface EmployeeAbsence {
  id: string;
  employeeId: string;
  absenceType: AbsenceTypeKey;
  dateFrom: string;
  dateTo: string;
  days: number;
  reason: string;
  details: string | null;
  status: AbsenceStatusKey;
  revision: number;
}

export interface VacationBalance {
  year: number;
  entitlement: number;
  used: number;
  remaining: number;
}

export interface EmployeeAbsences {
  items: EmployeeAbsence[];
  vacationBalance: VacationBalance;
}

export type EmployeeFunctionScope = 'collection' | 'employee';

export interface EmployeeFunctionDescriptor {
  key: string;
  title: string;
  description: string;
  scope: EmployeeFunctionScope;
}

export interface CoreEmployeeRecord {
  id: string;
  revision: number;
  employmentStatus: string;
  active: boolean;
  terminationDate: string | null;
}

export interface StaffingSlotOption {
  id: string;
  label: string;
}

export interface HrOverview {
  totalEmployees: number;
  activeEmployees: number;
  onProbation: number;
  onLeave: number;
  onSickLeave: number;
  onBusinessTrip: number;
  onboardingCases: number;
  overdueTasks: number;
  incompleteFiles: number;
  expiringContracts: number;
  activeProcesses: number;
}
