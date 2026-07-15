import { Inject, Injectable } from '@nestjs/common';
import { RequestContext } from '../auth/auth.types';
import { errors } from '../common/domain-error';
import { CreateEmployeeDto, EmployeeQueryDto } from './dto/employee.dto';
import { EmployeeRecord, HR_REPOSITORY, HrRepository } from './hr.repository';

@Injectable()
export class EmployeeService {
  constructor(@Inject(HR_REPOSITORY) private readonly repository: HrRepository) {}

  async list(query: EmployeeQueryDto, context: RequestContext) {
    if (!context.permissions.includes('hr.employee.read.all')) throw errors.forbidden('hr.employee.read.all');
    const result = await this.repository.listEmployees(query);
    return { ...result, items: result.items.map((item) => this.present(item, context)) };
  }

  async get(id: string, context: RequestContext) {
    const employee = await this.repository.getEmployee(id);
    if (!employee) throw errors.notFound('employee');
    const canRead = context.permissions.includes('hr.employee.read.all')
      || (context.permissions.includes('hr.employee.read.self') && context.employeeId === employee.id)
      || (context.permissions.includes('hr.employee.read.team') && employee.managerId === context.employeeId);
    if (!canRead) {
      await this.repository.recordSecurityAudit('Employee', id, 'EmployeeAccessDenied', context, 'ABAC policy denied employee profile access');
      throw errors.forbidden();
    }
    return this.present(employee, context);
  }

  async create(dto: CreateEmployeeDto, context: RequestContext) {
    const employee = await this.repository.createEmployee({
      ...dto,
      startDate: new Date(dto.startDate),
      contractEndDate: dto.contractEndDate ? new Date(dto.contractEndDate) : undefined,
      probationEndDate: dto.probationEndDate ? new Date(dto.probationEndDate) : undefined
    }, context);
    return this.present(employee, context);
  }

  async overview() {
    return { ...(await this.repository.getOverview()), onBusinessTrip: 0, onboardingCases: 0, overdueTasks: 0, activeProcesses: 0 };
  }

  private present(employee: EmployeeRecord, context: RequestContext) {
    if (context.permissions.includes('hr.compensation.read')) return employee;
    const { salary: _salary, currency: _currency, ...safeEmployee } = employee;
    void _salary;
    void _currency;
    return safeEmployee;
  }
}
