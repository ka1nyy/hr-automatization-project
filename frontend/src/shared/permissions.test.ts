import { describe, expect, it } from 'vitest';
import { getPermissions } from './permissions';

describe('permission matrix', () => {
  it('keeps registration with the secretariat persona', () => {
    expect(getPermissions('secretary')).toContain('correspondence.register');
    expect(getPermissions('employee')).not.toContain('correspondence.register');
  });

  it('restricts process editing to process designers', () => {
    expect(getPermissions('process-designer')).toContain('workflow.definition.edit');
    expect(getPermissions('executive')).not.toContain('workflow.definition.edit');
  });

  it('allows the primary chairman account to approve the final hiring stage', () => {
    expect(getPermissions('executive')).toContain('hiring.approve');
  });

  it('temporarily exposes the HR workspace permissions to every persona', () => {
    expect(getPermissions('employee')).toContain('hr.leave.create');
    expect(getPermissions('employee')).toContain('hr.employees.read');
    expect(getPermissions('employee')).toContain('hr.sensitive.read');
    expect(getPermissions('secretary')).toContain('hr.read');
    expect(getPermissions('accountant')).toContain('hr.leave.review');

    expect(getPermissions('hr-specialist')).toContain('hr.employees.read');
    expect(getPermissions('hr-specialist')).toContain('hr.sensitive.read');
    expect(getPermissions('hr-specialist')).toContain('hr.leave.review');
  });
});
