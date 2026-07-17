import type { HrEmployeeStatus, LeaveRequestStatus } from '../model/types';

const employeeLabels: Record<HrEmployeeStatus, string> = { active: 'Активен', probation: 'Испытательный срок', on_leave: 'В отпуске', sick_leave: 'Больничный', business_trip: 'В командировке' };
const leaveLabels: Record<LeaveRequestStatus, string> = { pending_manager: 'У руководителя', hr_review: 'Проверка HR', approved: 'Одобрено', rejected: 'Отклонено' };

export function EmployeeStatus({ status }: { status: HrEmployeeStatus }) {
  return <span className={`hr-status hr-status-${status}`}><i />{employeeLabels[status]}</span>;
}

export function LeaveStatus({ status }: { status: LeaveRequestStatus }) {
  return <span className={`hr-status hr-status-${status}`}><i />{leaveLabels[status]}</span>;
}
