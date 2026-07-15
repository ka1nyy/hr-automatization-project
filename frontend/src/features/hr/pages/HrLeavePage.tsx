import { useState } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, CalendarCheck2, Check, CheckCircle2, Clock3, FileText, ShieldCheck, X } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { PageHeader, QueryState, Section } from '../../../shared/components';
import { formatDate } from '../../../shared/format';
import { usePermission } from '../../../shared/permissions';
import { useDeveloperStore } from '../../../shared/store';
import { hrRepository } from '../api';
import { LeaveStatus } from '../components/HrStatus';
import { calculateLeaveDays, leaveRequestSchema, type LeaveRequestForm } from '../model/schemas';

const errorLabels: Record<string, string> = {
  HR_LEAVE_BALANCE_EXCEEDED: 'Недостаточно дней отпуска для выбранного периода.',
  HR_EMPLOYEE_NOT_FOUND: 'Профиль сотрудника не найден.',
  HR_LEAVE_REQUEST_NOT_FOUND: 'Заявка больше не доступна.'
};

export default function HrLeavePage() {
  const persona = useDeveloperStore((state) => state.persona);
  const locale = useDeveloperStore((state) => state.locale);
  const isHr = persona === 'hr-specialist';
  const canReview = usePermission('hr.leave.review');
  const [successNumber, setSuccessNumber] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const requests = useQuery({ queryKey: ['hr', 'leave'], queryFn: () => hrRepository.listLeaveRequests() });
  const employee = useQuery({ queryKey: ['hr', 'employee', 'e-3'], queryFn: () => hrRepository.getEmployee('e-3'), enabled: !isHr });
  const form = useForm<LeaveRequestForm>({ resolver: zodResolver(leaveRequestSchema), mode: 'onChange', defaultValues: { leaveType: 'Ежегодный оплачиваемый', startDate: '2026-08-17', endDate: '2026-08-21', substitute: '', comment: '' } });
  const createMutation = useMutation({ mutationFn: (input: LeaveRequestForm) => hrRepository.createLeaveRequest({ ...input, employeeId: 'e-3' }), onSuccess: async (created) => { setSuccessNumber(created.documentNumber); form.reset(); await queryClient.invalidateQueries({ queryKey: ['hr'] }); } });
  const reviewMutation = useMutation({ mutationFn: ({ id, decision }: { id: string; decision: 'approve' | 'reject' }) => hrRepository.reviewLeaveRequest(id, decision), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['hr'] }) });
  if (requests.isLoading || employee.isLoading) return <QueryState />;
  const error = requests.error || employee.error;
  if (error) return <QueryState error={error} retry={() => { requests.refetch(); employee.refetch(); }} />;

  const watchedStart = form.watch('startDate');
  const watchedEnd = form.watch('endDate');
  const requestedDays = watchedStart && watchedEnd ? calculateLeaveDays(watchedStart, watchedEnd) : 0;
  const visibleRequests = isHr ? requests.data! : requests.data!.filter((item) => item.employeeId === 'e-3');

  return <>
    <PageHeader eyebrow={isHr ? 'HR · Absence management' : 'HR · Self service'} title={isHr ? 'Управление отпусками' : 'Мои отпуска'} description={isHr ? 'Проверка заявок, балансов и workflow-статусов сотрудников.' : 'Баланс, история и новая заявка на отпуск.'} />
    {successNumber && <div className="success-banner"><CheckCircle2 size={20} /><span><strong>Заявка создана</strong>Документ {successNumber} зарегистрирован, процесс Leave Request v2 запущен.</span><button className="icon-button" onClick={() => setSuccessNumber(null)}><X size={16} /></button></div>}
    {isHr ? <>
      <div className="hr-leave-summary"><article><span>На проверке HR</span><strong>{visibleRequests.filter((item) => item.status === 'hr_review').length}</strong><small>Нужны действия</small></article><article><span>У руководителей</span><strong>{visibleRequests.filter((item) => item.status === 'pending_manager').length}</strong><small>Ожидают решения</small></article><article><span>Одобрено в июле</span><strong>18</strong><small>142 календарных дня</small></article><article><span>Конфликты графика</span><strong className="text-coral">2</strong><small>Требуют согласования</small></article></div>
      <Section title="Очередь заявок" meta={`${visibleRequests.length} записей`}><div className="data-table-wrap borderless"><table className="data-table hr-leave-table"><thead><tr><th>Сотрудник</th><th>Период</th><th>Тип</th><th>Документ / процесс</th><th>Статус</th><th>Действия</th></tr></thead><tbody>{visibleRequests.map((request) => <tr key={request.id}><td><strong>{request.employeeName}</strong><small>{request.substitute} · замещение</small></td><td>{formatDate(request.startDate, locale, 'dd MMM')} — {formatDate(request.endDate, locale, 'dd MMM yyyy')}<small>{request.days} календарных дней</small></td><td>{request.leaveType}</td><td><strong className="text-teal">{request.documentNumber}</strong><small>{request.workflowStep}</small></td><td><LeaveStatus status={request.status} /></td><td>{canReview && request.status === 'hr_review' ? <div className="hr-review-actions"><button className="approve" onClick={() => reviewMutation.mutate({ id: request.id, decision: 'approve' })} title="Подтвердить"><Check size={15} /></button><button className="reject" onClick={() => reviewMutation.mutate({ id: request.id, decision: 'reject' })} title="Отклонить"><X size={15} /></button></div> : <span className="hr-action-muted">Нет действий</span>}</td></tr>)}</tbody></table></div></Section>
    </> : <div className="hr-leave-layout">
      <form onSubmit={form.handleSubmit((value) => createMutation.mutate(value))}>
        <Section title="Новая заявка" meta="Leave Request v2"><div className="field-grid hr-leave-form">
          <label className="span-two">Тип отпуска<select {...form.register('leaveType')}><option>Ежегодный оплачиваемый</option><option>Без сохранения заработной платы</option><option>Учебный отпуск</option><option>Социальный отпуск</option></select></label>
          <label>Дата начала<input type="date" {...form.register('startDate')} />{form.formState.errors.startDate && <em>{form.formState.errors.startDate.message}</em>}</label>
          <label>Дата окончания<input type="date" {...form.register('endDate')} />{form.formState.errors.endDate && <em>{form.formState.errors.endDate.message}</em>}</label>
          <label className="span-two">Замещающий сотрудник<input {...form.register('substitute')} placeholder="Начните вводить ФИО" />{form.formState.errors.substitute && <em>{form.formState.errors.substitute.message}</em>}</label>
          <label className="span-two">Комментарий<textarea rows={3} {...form.register('comment')} placeholder="Дополнительная информация для руководителя" /></label>
          <div className="hr-route-preview span-two"><span><CheckCircle2 size={15} />Сотрудник</span><i /><span><Clock3 size={15} />Руководитель</span><i /><span><ShieldCheck size={15} />HR проверка</span><i /><span><CalendarCheck2 size={15} />Календарь</span></div>
        </div><div className="hr-form-footer"><span>Будет создано заявление и workflow instance</span><button className="primary-button" disabled={!form.formState.isValid || createMutation.isPending}><FileText size={16} />{createMutation.isPending ? 'Отправка…' : 'Отправить заявку'}</button></div></Section>
        {createMutation.error && <div className="mutation-error hr-mutation-error"><AlertTriangle size={18} /><span><strong>Не удалось создать заявку</strong>{errorLabels[createMutation.error.message] ?? createMutation.error.message}</span></div>}
      </form>
      <aside className="hr-leave-aside">
        <Section title="Расчёт отпуска"><div className="hr-balance-detail"><span>Доступно</span><strong>{employee.data!.leaveBalance}<small>дней</small></strong><dl><div><dt>Запрошено</dt><dd>{Math.max(0, requestedDays)} дней</dd></div><div><dt>Останется</dt><dd className={requestedDays > employee.data!.leaveBalance ? 'text-coral' : ''}>{employee.data!.leaveBalance - Math.max(0, requestedDays)} дней</dd></div></dl></div></Section>
        <Section title="Мои заявки"><div className="hr-request-list compact">{visibleRequests.map((request) => <article key={request.id}><div><strong>{formatDate(request.startDate, locale, 'dd MMM')} — {formatDate(request.endDate, locale, 'dd MMM')}</strong><small>{request.documentNumber} · {request.days} дней</small></div><LeaveStatus status={request.status} /></article>)}</div></Section>
      </aside>
    </div>}
  </>;
}
