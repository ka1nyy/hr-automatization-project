import { beforeEach, describe, expect, it } from 'vitest';
import { MockHrRepository } from './mockHrRepository';

describe('MockHrRepository', () => {
  const repository = new MockHrRepository();

  beforeEach(async () => {
    await repository.reset();
  });

  it('creates an employee leave request with a document and workflow audit', async () => {
    const request = await repository.createLeaveRequest({
      employeeId: 'e-3',
      leaveType: 'Ежегодный оплачиваемый',
      startDate: '2026-10-05',
      endDate: '2026-10-09',
      comment: 'Плановый отпуск',
      substitute: 'Айдос Рахимов'
    });

    expect(request.status).toBe('pending_manager');
    expect(request.days).toBe(5);
    expect(request.documentNumber).toMatch(/^HR-LV-2026-/);
    expect(request.audit[0]?.detail).toContain(request.documentNumber);
  });

  it('rejects a request that exceeds the available balance', async () => {
    await expect(repository.createLeaveRequest({
      employeeId: 'e-3',
      leaveType: 'Ежегодный оплачиваемый',
      startDate: '2026-08-01',
      endDate: '2026-12-31',
      comment: '',
      substitute: ''
    })).rejects.toThrow('HR_LEAVE_BALANCE_EXCEEDED');
  });

  it('approves only an HR-review request and deducts the balance once', async () => {
    const before = await repository.getEmployee('emp-037');
    const request = await repository.reviewLeaveRequest('leave-102', 'approve');
    const after = await repository.getEmployee('emp-037');

    expect(request.status).toBe('approved');
    expect(after.leaveBalance).toBe(before.leaveBalance - request.days);
    await expect(repository.reviewLeaveRequest('leave-102', 'approve'))
      .rejects.toThrow('HR_LEAVE_REQUEST_NOT_REVIEWABLE');
  });
});
