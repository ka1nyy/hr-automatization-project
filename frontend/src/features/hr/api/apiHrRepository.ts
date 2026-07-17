import { ApiClient } from '../../../repositories/apiRepositories';
import type {
  CoreEmployeeRecord,
  EmployeeAbsence,
  EmployeeAbsences,
  EmployeeFunctionDescriptor,
  HrEmployee,
  HrOverview,
  InitiateTerminationInput,
  LeaveRequest,
  StaffingSlotOption,
  TerminationCase,
  TerminationReason
} from '../model/types';
import type { HrRepository } from './contracts';

type StructureUnit = { id: string; name: string };
type StructureNode = { unit: StructureUnit; children: StructureNode[] };
type StructureSlot = { id: string; organizationUnitId: string; positionDefinitionId: string; status: string };
type StructureView = { root: StructureNode | null; staffingSlots: StructureSlot[] };
type PositionDefinition = { id: string; name: string };

type CoreAssignment = {
  id: string;
  staffingSlotId: string;
  assignmentType: string;
  effectiveFrom: string;
  effectiveTo: string | null;
  primary: boolean;
  status: string;
};

type CoreEmployee = {
  id: string;
  employeeNumber: string;
  displayName: string;
  employmentStatus: string;
  hireDate: string;
  probationEnd?: string | null;
  terminationDate: string | null;
  corporateEmail: string | null;
  active: boolean;
  revision: number;
  assignments: CoreAssignment[];
};

/** Position and unit names resolved from the active published structure. */
type Directory = {
  unitNames: Map<string, string>;
  positionNames: Map<string, string>;
  slots: Map<string, StructureSlot>;
};

function flattenUnits(node: StructureNode | null, into: Map<string, string>) {
  if (!node) return into;
  into.set(node.unit.id, node.unit.name);
  node.children.forEach((child) => flattenUnits(child, into));
  return into;
}

function initials(name: string) {
  return name.split(' ').slice(0, 2).map((part) => part[0] ?? '').join('').toUpperCase();
}

export function isProbationActive(probationEnd: string | null | undefined, today = new Date().toISOString().slice(0, 10)) {
  return Boolean(probationEnd && probationEnd >= today);
}

function primaryAssignment(employee: CoreEmployee) {
  return employee.assignments.find((item) => item.primary && (item.status === 'active' || item.status === 'scheduled_end'))
    ?? employee.assignments.find((item) => item.primary && item.status === 'planned')
    ?? null;
}

function toHrEmployee(employee: CoreEmployee, directory: Directory, activeAbsence?: EmployeeAbsence, leaveBalance = 24): HrEmployee {
  const assignment = primaryAssignment(employee);
  const slot = assignment ? directory.slots.get(assignment.staffingSlotId) : undefined;
  const unitId = slot?.organizationUnitId ?? null;
  const onProbation = isProbationActive(employee.probationEnd);
  const completeness = 50 + (employee.corporateEmail ? 25 : 0) + (assignment ? 25 : 0);
  const absenceStatus = activeAbsence?.absenceType === 'sick_leave'
    ? 'sick_leave'
    : activeAbsence?.absenceType === 'vacation' || activeAbsence?.absenceType === 'day_off'
      ? 'on_leave'
      : activeAbsence?.absenceType === 'business_trip'
        ? 'business_trip'
        : null;
  return {
    id: employee.id,
    unitId,
    employeeNumber: employee.employeeNumber,
    fullName: employee.displayName,
    initials: initials(employee.displayName),
    position: (slot && directory.positionNames.get(slot.positionDefinitionId)) ?? 'Должность не назначена',
    department: (slot && directory.unitNames.get(slot.organizationUnitId)) ?? 'Подразделение не назначено',
    manager: null,
    workEmail: employee.corporateEmail ?? '',
    phone: '',
    startDate: employee.hireDate,
    location: 'Павлодар',
    status: absenceStatus ?? (onProbation ? 'probation' : 'active'),
    availability: activeAbsence ? 'away' : 'available',
    employmentType: assignment?.assignmentType ?? 'not_assigned',
    contractEnd: assignment?.effectiveTo ?? null,
    probationEnd: employee.probationEnd ?? null,
    leaveBalance,
    personnelFileCompleteness: completeness,
    salary: 0,
    currency: 'KZT',
    skills: []
  };
}

const ABSENCE_MODULE_MESSAGE = 'Модуль отпусков и заявок ещё не перенесён на новый бэкенд.';

export class ApiHrRepository implements HrRepository {
  private directoryPromise: Promise<Directory> | null = null;

  constructor(private readonly api = new ApiClient()) {}

  private directory(): Promise<Directory> {
    this.directoryPromise ??= Promise.all([
      this.api.get<StructureView>('/organization/structure/active'),
      this.api.get<PositionDefinition[]>('/positions?pageSize=100')
    ]).then(([structure, positions]) => ({
      unitNames: flattenUnits(structure.root, new Map<string, string>()),
      positionNames: new Map(positions.map((item) => [item.id, item.name])),
      slots: new Map(structure.staffingSlots.map((slot) => [slot.id, slot]))
    })).catch((error: unknown) => {
      this.directoryPromise = null;
      throw error;
    });
    return this.directoryPromise;
  }

  async listEmployees() {
    const [employees, directory, activeAbsences] = await Promise.all([
      this.api.get<CoreEmployee[]>('/employees?pageSize=200&active=true'),
      this.directory(),
      this.listActiveAbsences().catch(() => [] as EmployeeAbsence[])
    ]);
    const absenceByEmployee = new Map(activeAbsences.map((absence) => [absence.employeeId, absence]));
    return employees
      .filter((employee) => employee.employmentStatus !== 'ended')
      .map((employee) => toHrEmployee(employee, directory, absenceByEmployee.get(employee.id)));
  }

  async getEmployee(id: string) {
    const [employee, directory, absences] = await Promise.all([
      this.api.get<CoreEmployee>(`/employees/${id}`),
      this.directory(),
      this.listAbsences(id).catch(() => null)
    ]);
    const activeAbsence = absences?.items.find((item) => item.status === 'active');
    return toHrEmployee(employee, directory, activeAbsence, absences?.vacationBalance.remaining ?? 24);
  }

  async getCurrentEmployee() {
    const [employee, directory] = await Promise.all([
      this.api.get<CoreEmployee>('/employees/me'),
      this.directory()
    ]);
    return toHrEmployee(employee, directory);
  }

  listAbsences(employeeId: string) {
    return this.api.get<EmployeeAbsences>(`/employees/${employeeId}/absences`);
  }

  private organizationIdPromise: Promise<string> | null = null;

  private organizationId(): Promise<string> {
    this.organizationIdPromise ??= this.api
      .get<{ id: string }>('/organization')
      .then((organization) => organization.id)
      .catch((error: unknown) => {
        this.organizationIdPromise = null;
        throw error;
      });
    return this.organizationIdPromise;
  }

  async listTerminationReasons(unitId?: string | null): Promise<TerminationReason[]> {
    const organizationId = await this.organizationId();
    const unit = unitId ? `&unitId=${unitId}` : '';
    return this.api.get<TerminationReason[]>(`/terminations/reasons?organizationId=${organizationId}${unit}`);
  }

  async listTerminationCases(employeeId: string): Promise<TerminationCase[]> {
    const organizationId = await this.organizationId();
    const rows = await this.api.get<TerminationCase[]>(`/terminations?organizationId=${organizationId}&pageSize=100`);
    return rows.filter((row) => row.employee_id === employeeId);
  }

  async initiateTermination(input: InitiateTerminationInput): Promise<TerminationCase> {
    const organizationId = await this.organizationId();
    return this.api.post<TerminationCase>('/terminations', { organizationId, ...input });
  }

  async decideTermination(caseId: string, decision: 'approve' | 'return' | 'reject', comment: string, revision: number): Promise<TerminationCase> {
    const organizationId = await this.organizationId();
    return this.api.post<TerminationCase>(`/terminations/${caseId}/hr-review`, { organizationId, revision, decision, comment });
  }

  async cancelTermination(caseId: string, revision: number, reason: string): Promise<TerminationCase> {
    const organizationId = await this.organizationId();
    return this.api.post<TerminationCase>(`/terminations/${caseId}/cancel`, { organizationId, revision, reason });
  }

  listActiveAbsences() {
    return this.api.get<EmployeeAbsence[]>('/absences');
  }

  async getOverview(): Promise<HrOverview> {
    const [employees, activeAbsences] = await Promise.all([
      this.listEmployees(),
      this.listActiveAbsences()
    ]);
    const horizon = new Date();
    horizon.setDate(horizon.getDate() + 90);
    const byType = (type: EmployeeAbsence['absenceType']) =>
      activeAbsences.filter((item) => item.absenceType === type).length;
    return {
      totalEmployees: employees.length,
      activeEmployees: employees.filter((item) => item.status === 'active').length,
      onProbation: employees.filter((item) => item.status === 'probation').length,
      onLeave: byType('vacation') + byType('day_off'),
      onSickLeave: byType('sick_leave'),
      onBusinessTrip: byType('business_trip'),
      onboardingCases: 0,
      overdueTasks: 0,
      incompleteFiles: employees.filter((item) => item.personnelFileCompleteness < 90).length,
      expiringContracts: employees.filter(
        (item) => item.contractEnd !== null && new Date(item.contractEnd) <= horizon
      ).length,
      activeProcesses: 0
    };
  }

  async listLeaveRequests(): Promise<LeaveRequest[]> {
    return [];
  }

  async createLeaveRequest(): Promise<LeaveRequest> {
    throw new Error(ABSENCE_MODULE_MESSAGE);
  }

  async reviewLeaveRequest(): Promise<LeaveRequest> {
    throw new Error(ABSENCE_MODULE_MESSAGE);
  }

  async submitHiringRequest(): Promise<{ id: string; number: string; status: string; currentStep: string }> {
    throw new Error('Заявки на найм заменены функцией employee.hire нового бэкенда.');
  }

  listCollectionFunctions() { return this.api.get<EmployeeFunctionDescriptor[]>('/employees/functions'); }
  listEmployeeFunctions(employeeId: string) { return this.api.get<EmployeeFunctionDescriptor[]>(`/employees/${employeeId}/functions`); }
  invokeEmployeeFunction(employeeId: string, key: string, payload: Record<string, unknown>) {
    return this.api.post<unknown>(`/employees/${employeeId}/functions/${key}`, { payload });
  }
  invokeCollectionFunction(key: string, payload: Record<string, unknown>) {
    return this.api.post<CoreEmployee>(`/employees/functions/${key}`, { payload });
  }
  getCoreEmployee(employeeId: string) { return this.api.get<CoreEmployeeRecord>(`/employees/${employeeId}`); }

  async listVacantSlots(): Promise<StaffingSlotOption[]> {
    const directory = await this.directory();
    return [...directory.slots.values()]
      .filter((slot) => slot.status === 'vacant' || slot.status === 'approved')
      .map((slot) => ({
        id: slot.id,
        label: [
          directory.positionNames.get(slot.positionDefinitionId) ?? 'Должность',
          directory.unitNames.get(slot.organizationUnitId) ?? 'Подразделение'
        ].join(' · ')
      }))
      .sort((left, right) => left.label.localeCompare(right.label, 'ru'));
  }

  async reset() { /* Server records and audit history are intentionally immutable. */ }
}
