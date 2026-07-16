import { ApiClient } from '../../../repositories/apiRepositories';
import type {
  CoreEmployeeRecord,
  EmployeeFunctionDescriptor,
  HrEmployee,
  HrOverview,
  LeaveRequest,
  StaffingSlotOption
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

function primaryAssignment(employee: CoreEmployee) {
  return employee.assignments.find((item) => item.primary && (item.status === 'active' || item.status === 'scheduled_end'))
    ?? employee.assignments.find((item) => item.primary && item.status === 'planned')
    ?? null;
}

const PROBATION_DAYS = 90;

function toHrEmployee(employee: CoreEmployee, directory: Directory): HrEmployee {
  const assignment = primaryAssignment(employee);
  const slot = assignment ? directory.slots.get(assignment.staffingSlotId) : undefined;
  const probationEnd = new Date(employee.hireDate);
  probationEnd.setDate(probationEnd.getDate() + PROBATION_DAYS);
  const onProbation = employee.employmentStatus === 'draft' || probationEnd > new Date();
  const completeness = 50 + (employee.corporateEmail ? 25 : 0) + (assignment ? 25 : 0);
  return {
    id: employee.id,
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
    status: onProbation ? 'probation' : 'active',
    availability: 'available',
    employmentType: assignment?.assignmentType ?? 'not_assigned',
    contractEnd: assignment?.effectiveTo ?? null,
    probationEnd: probationEnd > new Date() ? probationEnd.toISOString().slice(0, 10) : null,
    leaveBalance: 24,
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
    const [employees, directory] = await Promise.all([
      this.api.get<CoreEmployee[]>('/employees?pageSize=200&active=true'),
      this.directory()
    ]);
    return employees
      .filter((employee) => employee.employmentStatus !== 'ended')
      .map((employee) => toHrEmployee(employee, directory));
  }

  async getEmployee(id: string) {
    const [employee, directory] = await Promise.all([
      this.api.get<CoreEmployee>(`/employees/${id}`),
      this.directory()
    ]);
    return toHrEmployee(employee, directory);
  }

  async getCurrentEmployee() {
    const [employee, directory] = await Promise.all([
      this.api.get<CoreEmployee>('/employees/me'),
      this.directory()
    ]);
    return toHrEmployee(employee, directory);
  }

  async getOverview(): Promise<HrOverview> {
    const employees = await this.listEmployees();
    const horizon = new Date();
    horizon.setDate(horizon.getDate() + 90);
    return {
      totalEmployees: employees.length,
      activeEmployees: employees.filter((item) => item.status === 'active').length,
      onProbation: employees.filter((item) => item.status === 'probation').length,
      onLeave: 0,
      onSickLeave: 0,
      onBusinessTrip: 0,
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
