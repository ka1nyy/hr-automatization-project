import { calculateLeaveDays } from '../model/schemas';
import type { CreateLeaveRequestInput, HrEmployee, LeaveRequest } from '../model/types';
import { hrEmployeeFixtures, leaveRequestFixtures } from '../mocks/fixtures';
import type { HrRepository } from './contracts';

const STORAGE_KEY = 'ertis-hr-mock-v1';
type HrDatabase = { employees: HrEmployee[]; leaveRequests: LeaveRequest[] };
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
const seed = (): HrDatabase => ({ employees: clone(hrEmployeeFixtures), leaveRequests: clone(leaveRequestFixtures) });

function read(): HrDatabase {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (!stored) return seed();
  try { return JSON.parse(stored) as HrDatabase; } catch { return seed(); }
}

function write(database: HrDatabase) { localStorage.setItem(STORAGE_KEY, JSON.stringify(database)); }
const wait = async <T,>(value: T) => new Promise<T>((resolve) => window.setTimeout(() => resolve(clone(value)), 100));

export class MockHrRepository implements HrRepository {
  async getOverview() {
    const database = read();
    return wait({
      totalEmployees: 180,
      activeEmployees: 180,
      onProbation: database.employees.filter((item) => item.status === 'probation').length + 11,
      onLeave: database.employees.filter((item) => item.status === 'on_leave').length + 14,
      onSickLeave: database.employees.filter((item) => item.status === 'sick_leave').length + 3,
      onBusinessTrip: 3,
      onboardingCases: 7,
      overdueTasks: 4,
      incompleteFiles: database.employees.filter((item) => item.personnelFileCompleteness < 90).length + 9,
      expiringContracts: database.employees.filter((item) => item.contractEnd?.startsWith('2026')).length + 5,
      activeProcesses: 14
    });
  }

  async listEmployees() { return wait(read().employees); }

  async getEmployee(id: string) {
    const employee = read().employees.find((item) => item.id === id);
    if (!employee) throw new Error('HR_EMPLOYEE_NOT_FOUND');
    return wait(employee);
  }

  async getCurrentEmployee() { return this.getEmployee('e-3'); }

  async listLeaveRequests() { return wait(read().leaveRequests); }

  async createLeaveRequest(input: CreateLeaveRequestInput) {
    const database = read();
    const employee = database.employees.find((item) => item.id === input.employeeId);
    if (!employee) throw new Error('HR_EMPLOYEE_NOT_FOUND');
    const days = calculateLeaveDays(input.startDate, input.endDate);
    if (days <= 0 || days > employee.leaveBalance) throw new Error('HR_LEAVE_BALANCE_EXCEEDED');
    const sequence = 104 + database.leaveRequests.filter((item) => item.id.startsWith('leave-new')).length;
    const documentNumber = `HR-LV-2026-${String(sequence).padStart(4, '0')}`;
    const request: LeaveRequest = {
      id: `leave-new-${sequence}`,
      employeeId: employee.id,
      employeeName: employee.fullName,
      leaveType: input.leaveType,
      startDate: input.startDate,
      endDate: input.endDate,
      days,
      comment: input.comment,
      substitute: input.substitute,
      status: 'pending_manager',
      documentNumber,
      workflowStep: 'Согласование руководителем',
      createdAt: new Date().toISOString(),
      audit: [{ id: `hr-audit-${sequence}`, at: new Date().toISOString(), actor: employee.fullName, action: 'Заявка создана', detail: `Создан документ ${documentNumber} и запущен Leave Request v2` }]
    };
    database.leaveRequests.unshift(request);
    write(database);
    return wait(request);
  }

  async reviewLeaveRequest(id: string, decision: 'approve' | 'reject') {
    const database = read();
    const request = database.leaveRequests.find((item) => item.id === id);
    if (!request) throw new Error('HR_LEAVE_REQUEST_NOT_FOUND');
    if (request.status !== 'hr_review') throw new Error('HR_LEAVE_REQUEST_NOT_REVIEWABLE');
    request.status = decision === 'approve' ? 'approved' : 'rejected';
    request.workflowStep = decision === 'approve' ? 'Завершено' : 'Отклонено HR';
    request.audit.unshift({ id: `hr-audit-${Date.now()}`, at: new Date().toISOString(), actor: 'Зарина Ахметова', action: decision === 'approve' ? 'HR проверка выполнена' : 'Заявка отклонена', detail: decision === 'approve' ? 'Баланс подтверждён, календарь обновлён' : 'Требуется корректировка данных' });
    if (decision === 'approve') {
      const employee = database.employees.find((item) => item.id === request.employeeId);
      if (employee) employee.leaveBalance -= request.days;
    }
    write(database);
    return wait(request);
  }

  async submitHiringRequest() {
    return wait({ id: 'mock-hiring', number: 'HR-HIRE-MOCK', status: 'on_check', currentStep: 'HR completeness check' });
  }

  async listCollectionFunctions() {
    return wait([
      {
        key: 'employee.hire',
        title: 'Нанять сотрудника',
        description: 'Создать сотрудника и назначить его на штатную единицу.',
        scope: 'collection' as const
      }
    ]);
  }

  async listEmployeeFunctions(employeeId: string) {
    const employee = read().employees.find((item) => item.id === employeeId);
    if (!employee) return wait([]);
    return wait([
      {
        key: 'employee.terminate',
        title: 'Уволить сотрудника',
        description: 'Завершить трудовые отношения и закрыть активные назначения.',
        scope: 'employee' as const
      },
      {
        key: 'employee.transfer',
        title: 'Перевести сотрудника',
        description: 'Перевести сотрудника на другую штатную единицу.',
        scope: 'employee' as const
      }
    ]);
  }

  async invokeEmployeeFunction(employeeId: string, key: string) {
    return wait({ employeeId, key });
  }

  async getCoreEmployee(employeeId: string) {
    return wait({
      id: employeeId,
      revision: 1,
      employmentStatus: 'active',
      active: true,
      terminationDate: null
    });
  }

  async listVacantSlots() {
    return wait([{ id: 'slot-1', label: 'Специалист · IT Support' }]);
  }

  async listAbsences(employeeId: string) {
    void employeeId;
    return wait({
      items: [],
      vacationBalance: { year: new Date().getFullYear(), entitlement: 24, used: 0, remaining: 24 }
    });
  }

  async listActiveAbsences() {
    return wait([]);
  }

  async listTerminationReasons() {
    return wait([
      { id: 'reason-1', code: 'employee_request', name: 'По инициативе работника', legalReviewRequired: false }
    ]);
  }

  async listTerminationCases(employeeId: string) {
    void employeeId;
    return wait([]);
  }

  async initiateTermination(): Promise<never> {
    throw new Error('MOCK_TERMINATION_NOT_SUPPORTED');
  }

  async decideTermination(): Promise<never> {
    throw new Error('MOCK_TERMINATION_NOT_SUPPORTED');
  }

  async cancelTermination(): Promise<never> {
    throw new Error('MOCK_TERMINATION_NOT_SUPPORTED');
  }

  async reset() { localStorage.removeItem(STORAGE_KEY); }
}
