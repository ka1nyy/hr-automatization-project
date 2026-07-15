import { Controller, Get, Param, ParseUUIDPipe, Query } from '@nestjs/common';
import { ApiOperation, ApiSecurity, ApiTags } from '@nestjs/swagger';
import { CurrentContext } from '../auth/request-context';
import { RequestContext } from '../auth/auth.types';
import { RequirePermissions } from '../auth/permissions.decorator';
import { EmployeeQueryDto } from './dto/employee.dto';
import { EmployeeService } from './employee.service';

@ApiTags('HR employees')
@ApiSecurity('dev-user-id')
@RequirePermissions('hr.read')
@Controller('api/v1/hr')
export class EmployeeController {
  constructor(private readonly employees: EmployeeService) {}

  @Get('overview')
  @RequirePermissions('hr.employee.read.all')
  @ApiOperation({ summary: 'Get HR operational counters' })
  overview() { return this.employees.overview(); }

  @Get('dashboard')
  @RequirePermissions('hr.employee.read.all')
  @ApiOperation({ summary: 'Get aggregated HR dashboard metrics' })
  dashboard() { return this.employees.overview(); }

  @Get('employees')
  @ApiOperation({ summary: 'List employees (HR only)' })
  list(@Query() query: EmployeeQueryDto, @CurrentContext() context: RequestContext) {
    return this.employees.list(query, context);
  }

  @Get('employees/:id')
  @ApiOperation({ summary: 'Get employee using self/team/all ABAC policy' })
  get(@Param('id', ParseUUIDPipe) id: string, @CurrentContext() context: RequestContext) {
    return this.employees.get(id, context);
  }

}
