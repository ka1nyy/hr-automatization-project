import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarClock, Check, CheckCircle2, ClipboardCheck, FileCheck2, ShieldCheck, Undo2, UserRound, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { PageHeader } from '../../../shared/components';
import { formatDate } from '../../../shared/format';
import { useDeveloperStore } from '../../../shared/store';
import { hrRepository } from '../api';
import {
  canActOnProcess,
  listWorkforceProcesses,
  processStatusLabels,
  workforceProcessesApi,
  type LeaveProcess,
  type ProcessDecision,
  type ProcessKind,
  type TerminationProcess,
  type TerminationTask,
  type TripProcess,
  type WorkforceProcess
} from '../api/workforceProcesses';

const pathByKind: Record<ProcessKind, string> = { leave: '/hr/leave', trip: '/hr/business-trips', termination: '/hr/terminations' };
const stages: Record<ProcessKind, Array<{ code: string; name: string }>> = {
  leave: [{ code: 'manager_review', name: 'Руководитель' }, { code: 'hr_review', name: 'HR-проверка' }, { code: 'approved', name: 'Календарь' }],
  trip: [{ code: 'manager_review', name: 'Руководитель' }, { code: 'finance_review', name: 'Финансы' }, { code: 'hr_registration', name: 'HR-регистрация' }, { code: 'registered', name: 'Календарь' }],
  termination: [{ code: 'hr_review', name: 'Директор HR' }, { code: 'economic_review', name: 'Экономический директор' }, { code: 'legal_review', name: 'Юридический департамент' }, { code: 'signature', name: 'Председатель правления' }, { code: 'registration', name: 'Приказ' }, { code: 'offboarding', name: 'Офбординг' }, { code: 'scheduled', name: 'Дата увольнения' }, { code: 'completed', name: 'Завершено' }]
};
const terminalStatuses = new Set(['approved', 'registered', 'completed', 'rejected', 'cancelled']);
const openStatuses = new Set(['manager_review', 'hr_review', 'economic_review', 'finance_review', 'hr_registration', 'legal_review', 'signature', 'registration', 'offboarding', 'scheduled', 'effective', 'returned']);
const taskLabels: Record<string, string> = {
  handover: 'Передача дел', asset_return: 'Возврат имущества', access_revocation: 'Закрытие доступов',
  settlement: 'Финальный расчёт', exit_interview: 'Выходное интервью'
};

function Timeline({ kind, status }: { kind: ProcessKind; status: string }) {
  const route = stages[kind];
  const active = route.findIndex((item) => item.code === status);
  const finished = ['approved', 'registered', 'completed'].includes(status);
  return <ol className="hiring-approval-timeline">{route.map((stage, index) => {
    const done = finished || (active >= 0 && index < active);
    return <li key={stage.code} className={done ? 'approve' : index === active ? 'current' : ''}><span>{done ? <Check size={16} /> : index + 1}</span><div><small>Этап {index + 1}</small><strong>{stage.name}</strong><p>{index === active ? 'Ожидает действия текущей роли' : done ? 'Завершено' : 'Ожидает предыдущий этап'}</p></div></li>;
  })}</ol>;
}

function TaskRow({ task, pending, canComplete, canWaive, onComplete, onWaive }: { task: TerminationTask; pending: boolean; canComplete: boolean; canWaive: boolean; onComplete: () => void; onWaive: () => void }) {
  return <article className={`offboarding-task ${task.status}`}><span>{task.status === 'completed' ? <CheckCircle2 size={18} /> : <ClipboardCheck size={18} />}</span><div><strong>{taskLabels[task.task_type] ?? task.task_type}</strong><small>{task.status === 'pending' ? canComplete || canWaive ? 'Ожидает вашего действия' : 'Ожидает ответственную роль' : task.status === 'waived' ? 'Пропущено с обоснованием' : task.status === 'completed' ? 'Выполнено' : 'Отменено'}</small></div>{task.status === 'pending' && (canComplete || canWaive) && <div>{canComplete && <button className="success-button compact" disabled={pending} onClick={onComplete}>Готово</button>}{canWaive && <button className="secondary-button compact" disabled={pending} onClick={onWaive}>Пропустить</button>}</div>}</article>;
}

export default function WorkforceProcessDetailsPage({ kind }: { kind: ProcessKind }) {
  const { id = '' } = useParams();
  const persona = useDeveloperStore((state) => state.persona);
  const locale = useDeveloperStore((state) => state.locale);
  const client = useQueryClient();
  const [comment, setComment] = useState('');
  const [effectiveDate, setEffectiveDate] = useState(new Date().toISOString().slice(0, 10));
  const [registrationNumber, setRegistrationNumber] = useState(`УВ-${new Date().getFullYear()}-`);
  const [registrationDate, setRegistrationDate] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState('');
  const query = useQuery({
    queryKey: ['workforce-process', kind, id, persona],
    queryFn: async () => {
      if (kind === 'termination') return workforceProcessesApi.getTermination(id);
      const rows = await listWorkforceProcesses(kind);
      const row = rows.find((entry) => entry.id === id);
      if (!row) throw new Error('Запись не найдена или недоступна для текущей роли.');
      return row;
    },
    enabled: Boolean(id)
  });
  const item = query.data as WorkforceProcess | undefined;
  const employees = useQuery({ queryKey: ['hr', 'employees'], queryFn: () => hrRepository.listEmployees() });
  const leaveTypes = useQuery({ queryKey: ['workforce-process', 'leave-types'], queryFn: workforceProcessesApi.listLeaveTypes, enabled: kind === 'leave' });
  const employee = employees.data?.find((person) => person.id === item?.employee_id);
  const coreEmployee = useQuery({
    queryKey: ['hr', 'employee-core', item?.employee_id],
    queryFn: () => hrRepository.getCoreEmployee(item!.employee_id),
    enabled: kind === 'termination' && Boolean(item?.employee_id)
  });
  const tasks = useQuery({
    queryKey: ['termination-tasks', id],
    queryFn: () => workforceProcessesApi.listTerminationTasks(id),
    enabled: kind === 'termination' && Boolean(item) && ['offboarding', 'scheduled', 'effective', 'completed'].includes(item?.status ?? '')
  });
  const invalidateLifecycle = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['workforce-process'] }),
      client.invalidateQueries({ queryKey: ['workforce-processes'] }),
      client.invalidateQueries({ queryKey: ['termination-tasks'] }),
      client.invalidateQueries({ queryKey: ['employee-absences'] }),
      client.invalidateQueries({ queryKey: ['hr'] })
    ]);
  };
  const action = useMutation({
    mutationFn: async (command: ProcessDecision | 'cancel' | 'register-order' | 'schedule' | 'complete' | 'resubmit') => {
      if (!item) throw new Error('Запись не загружена.');
      if ((command === 'return' || command === 'reject' || command === 'cancel') && !comment.trim()) throw new Error('Укажите причину решения.');
      if (command === 'cancel') {
        if (kind === 'leave') return workforceProcessesApi.cancelLeave(item as LeaveProcess, comment);
        if (kind === 'trip') return workforceProcessesApi.cancelTrip(item as TripProcess, comment);
        return workforceProcessesApi.cancelTermination(item as TerminationProcess, comment);
      }
      if (command === 'register-order') return workforceProcessesApi.createAndRegisterTerminationOrder(item as TerminationProcess, { registrationNumber, registrationDate });
      if (command === 'schedule') {
        const termination = item as TerminationProcess;
        const assignments = (coreEmployee.data?.assignments ?? []).filter((assignment) => assignment.id !== termination.primary_assignment_id && ['active', 'planned', 'scheduled_end'].includes(assignment.status));
        return workforceProcessesApi.scheduleTermination(termination, effectiveDate, assignments.map((assignment) => ({ assignmentId: assignment.id, action: 'end' as const })));
      }
      if (command === 'complete') return workforceProcessesApi.completeTermination(item as TerminationProcess);
      if (command === 'resubmit') {
        if (kind === 'leave') {
          const leave = item as LeaveProcess;
          return workforceProcessesApi.resubmitLeave(leave, { startDate: leave.start_date, endDate: leave.end_date, reason: comment || leave.reason || '' });
        }
        if (kind === 'trip') {
          const trip = item as TripProcess;
          return workforceProcessesApi.resubmitTrip(trip, { destination: trip.destination, startDate: trip.start_date, endDate: trip.end_date, purpose: trip.purpose, estimatedCost: trip.estimated_cost, currency: trip.currency, fundingDetails: trip.funding_details });
        }
        const termination = item as TerminationProcess;
        return workforceProcessesApi.resubmitTermination(termination, { employeeId: termination.employee_id, unitId: employee?.unitId ?? '', legalBasis: comment, requestedDate: termination.requested_date });
      }
      if (kind === 'leave') return workforceProcessesApi.decideLeave(item as LeaveProcess, command, comment);
      if (kind === 'trip') return workforceProcessesApi.decideTrip(item as TripProcess, command, comment);
      return workforceProcessesApi.decideTermination(item as TerminationProcess, command, comment);
    },
    onSuccess: async () => { setComment(''); setError(''); await invalidateLifecycle(); },
    onError: (value) => setError(value instanceof Error ? value.message : 'Действие не выполнено')
  });
  const taskAction = useMutation({
    mutationFn: async ({ task, mode }: { task: TerminationTask; mode: 'complete' | 'waive' }) => {
      if (mode === 'complete') return workforceProcessesApi.completeTerminationTask(task, { confirmedFrom: 'hr-portal' });
      const reason = window.prompt('Укажите причину, по которой задача не требуется:');
      if (!reason?.trim()) throw new Error('Для пропуска задачи нужна причина.');
      return workforceProcessesApi.waiveTerminationTask(task, reason);
    },
    onSuccess: invalidateLifecycle,
    onError: (value) => setError(value instanceof Error ? value.message : 'Задача не обновлена')
  });

  const leave = kind === 'leave' ? item as LeaveProcess | undefined : undefined;
  const trip = kind === 'trip' ? item as TripProcess | undefined : undefined;
  const termination = kind === 'termination' ? item as TerminationProcess | undefined : undefined;
  const canAct = item ? canActOnProcess(persona, kind, item.status) : false;
  const reviewStage = kind !== 'termination' || (item ? ['hr_review', 'economic_review', 'legal_review', 'signature'].includes(item.status) : false);
  const pendingTasks = useMemo(() => (tasks.data ?? []).filter((task) => task.status === 'pending').length, [tasks.data]);
  const hrPersona = ['hr-specialist', 'hr-initiator', 'hr-director'].includes(persona);
  const canCompleteTask = (taskType: string) => ({
    handover: persona === 'executive',
    asset_return: persona === 'accountant',
    access_revocation: persona === 'it-specialist',
    settlement: persona === 'accountant',
    exit_interview: hrPersona
  }[taskType] ?? false);
  const visibleTasks = useMemo(() => {
    if (hrPersona) return tasks.data ?? [];
    return (tasks.data ?? []).filter((task) => canCompleteTask(task.task_type));
  }, [hrPersona, persona, tasks.data]);

  if (query.isLoading || employees.isLoading) return <div className="hiring-empty">Загрузка процесса…</div>;
  if (!item) return <div className="api-error-card"><strong>Запись не найдена</strong><p>{query.error instanceof Error ? query.error.message : 'Проверьте доступ текущей роли.'}</p></div>;
  const employeeName = employee?.fullName ?? coreEmployee.data?.displayName ?? 'Сотрудник';
  const employeeDepartment = employee?.department ?? coreEmployee.data?.departmentName ?? '—';
  const subtitle = leave ? `${formatDate(leave.start_date, locale)} — ${formatDate(leave.end_date, locale)} · ${leave.requested_days} дней` : trip ? `${trip.destination} · ${formatDate(trip.start_date, locale)} — ${formatDate(trip.end_date, locale)}` : `Желаемая дата увольнения: ${formatDate(termination!.requested_date, locale)}`;
  const isEmployeeOwner = persona === 'employee';
  const canCancel = openStatuses.has(item.status) && (kind === 'termination' ? ['hr-specialist', 'hr-initiator', 'hr-director'].includes(persona) : isEmployeeOwner && item.status !== 'returned');

  const publicStatus = kind === 'termination' && !canAct && !hrPersona && !terminalStatuses.has(item.status) ? 'В обработке' : processStatusLabels[item.status] ?? item.status;

  return <>
    <PageHeader eyebrow={kind === 'leave' ? 'Заявка на отпуск' : kind === 'trip' ? 'Заявка на командировку' : 'Увольнение сотрудника'} title={employeeName} description={subtitle} actions={<><Link className="secondary-button" to={pathByKind[kind]}>Назад к очереди</Link>{employee && <Link className="secondary-button" to={`/hr/employees/${employee.id}`}><UserRound size={16} />Профиль</Link>}</>} />
    {error && <div className="api-error-card"><strong>Действие не выполнено</strong><p>{error}</p></div>}
    {terminalStatuses.has(item.status) && <div className={`lifecycle-result ${item.status}`}><CheckCircle2 size={21} /><div><strong>{processStatusLabels[item.status] ?? item.status}</strong><p>{item.status === 'approved' ? 'Отпуск зарегистрирован в календаре и отражён в профиле сотрудника.' : item.status === 'registered' ? 'Командировка зарегистрирована и отражена в профиле сотрудника.' : item.status === 'completed' ? 'Трудовые отношения завершены. Сотрудник исключён из активного состава.' : 'Маршрут закрыт, кадровые данные не изменены.'}</p></div></div>}
    <div className="hiring-detail-grid">
      <section className="hiring-detail-main"><header><span><ShieldCheck size={20} /></span><div><small>Статус заявки</small><strong>{publicStatus}</strong></div></header>
        <div className="hiring-summary-grid"><dl><dt>Сотрудник</dt><dd>{employeeName}</dd></dl><dl><dt>Подразделение</dt><dd>{employeeDepartment}</dd></dl>{trip && <><dl><dt>Бюджет</dt><dd>{new Intl.NumberFormat('ru-RU').format(trip.estimated_cost)} {trip.currency}</dd></dl><dl><dt>Цель</dt><dd>{trip.purpose}</dd></dl></>}{leave && <><dl><dt>Тип отпуска</dt><dd>{{ annual_paid: 'Ежегодный оплачиваемый отпуск', unpaid: 'Без сохранения заработной платы' }[leaveTypes.data?.find((type) => type.id === leave.leave_type_id)?.code ?? ''] ?? leaveTypes.data?.find((type) => type.id === leave.leave_type_id)?.name ?? 'Отпуск'}</dd></dl><dl><dt>Комментарий</dt><dd>{leave.reason || '—'}</dd></dl></>}{termination && <><dl><dt>Дата увольнения</dt><dd>{formatDate(termination.effective_date ?? termination.requested_date, locale)}</dd></dl><dl><dt>Приказ</dt><dd>{termination.order_document_id ? 'Зарегистрирован' : 'Будет сформирован после согласования'}</dd></dl></>}</div>
        {kind !== 'termination' && <><h3>Маршрут процесса</h3><Timeline kind={kind} status={item.status} /></>}
        {kind === 'termination' && <div className="termination-application-note"><FileCheck2 size={20} /><div><strong>Заявление и кадровые данные</strong><p>Основание, дата и зарегистрированный приказ хранятся в кадровом контуре. Пользователь видит только действие своей роли, без истории чужих согласований.</p></div></div>}
        {kind === 'termination' && ['offboarding', 'scheduled', 'effective', 'completed'].includes(item.status) && <div className="offboarding-block"><div className="offboarding-heading"><div><small>МОЯ ЗОНА ОТВЕТСТВЕННОСТИ</small><h3>{hrPersona ? 'Контроль офбординга' : 'Задачи офбординга'}</h3></div><span>{visibleTasks.filter((task) => task.status !== 'pending').length}/{visibleTasks.length}</span></div>{tasks.isLoading ? <p className="hr-empty-note">Загрузка задач…</p> : visibleTasks.length ? <div className="offboarding-list">{visibleTasks.map((task) => <TaskRow key={task.id} task={task} pending={taskAction.isPending} canComplete={canCompleteTask(task.task_type)} canWaive={hrPersona} onComplete={() => taskAction.mutate({ task, mode: 'complete' })} onWaive={() => taskAction.mutate({ task, mode: 'waive' })} />)}</div> : <p className="hr-empty-note">Для вашей роли открытых задач нет.</p>}</div>}
      </section>
      <aside className="hiring-document-panel"><h3><FileCheck2 size={18} />Действия</h3>
        {canAct && reviewStage && <div className="hiring-action-box"><label>Комментарий<textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Для возврата или отказа комментарий обязателен" /></label><div><button className="success-button" disabled={action.isPending} onClick={() => action.mutate('approve')}><Check size={16} />Согласовать</button><button className="secondary-button" disabled={action.isPending} onClick={() => action.mutate('return')}><Undo2 size={16} />Вернуть</button><button className="danger-button" disabled={action.isPending} onClick={() => action.mutate('reject')}><X size={16} />Отклонить</button></div></div>}
        {item.status === 'returned' && (isEmployeeOwner || (kind === 'termination' && hrPersona)) && <div className="hiring-action-box"><label>Комментарий к исправлениям<textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Что было исправлено" /></label><button className="primary-button full" disabled={action.isPending} onClick={() => action.mutate('resubmit')}><Undo2 size={16} />Отправить повторно</button></div>}
        {canAct && kind === 'termination' && item.status === 'registration' && <div className="hiring-action-box"><strong>Регистрация приказа</strong><label>Номер приказа<input value={registrationNumber} onChange={(event) => setRegistrationNumber(event.target.value)} /></label><label>Дата регистрации<input type="date" value={registrationDate} onChange={(event) => setRegistrationDate(event.target.value)} /></label><button className="primary-button full" disabled={!registrationNumber.trim() || action.isPending} onClick={() => action.mutate('register-order')}>Создать и зарегистрировать приказ</button><small>После регистрации backend автоматически направит задачи руководителю, бухгалтерии, IT и HR.</small></div>}
        {canAct && kind === 'termination' && item.status === 'offboarding' && <div className="hiring-action-box"><strong>Дата завершения</strong><label>Дата увольнения<input type="date" min={new Date().toISOString().slice(0, 10)} value={effectiveDate} onChange={(event) => setEffectiveDate(event.target.value)} /></label><button className="primary-button full" disabled={!effectiveDate || action.isPending || coreEmployee.isLoading} onClick={() => action.mutate('schedule')}><CalendarClock size={16} />Запланировать</button><small>Все дополнительные назначения будут завершены той же датой. Чек-лист можно закрывать параллельно.</small></div>}
        {canAct && kind === 'termination' && ['scheduled', 'effective'].includes(item.status) && <div className="hiring-action-box"><strong>Финальное завершение</strong><p>{pendingTasks ? `Осталось задач: ${pendingTasks}. Завершите или обоснованно пропустите их.` : 'Все задачи закрыты. После завершения сотрудник исчезнет из активного состава.'}</p><button className="primary-button full" disabled={action.isPending || pendingTasks > 0 || Boolean(termination?.effective_date && termination.effective_date > new Date().toISOString().slice(0, 10))} onClick={() => action.mutate('complete')}>Завершить увольнение</button></div>}
        {canCancel && <div className="hiring-action-box danger-zone"><label>Причина отмены<textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Обязательное основание" /></label><button className="danger-button full" disabled={action.isPending} onClick={() => action.mutate('cancel')}>Отменить процесс</button></div>}
        {!canAct && !canCancel && !terminalStatuses.has(item.status) && !(item.status === 'returned' && (isEmployeeOwner || (kind === 'termination' && hrPersona))) && visibleTasks.every((task) => task.status !== 'pending') && <div className="hiring-empty"><strong>Для вашей роли действий нет</strong><p>Заявка автоматически появится во входящих, когда потребуется ваше решение.</p></div>}
      </aside>
    </div>
  </>;
}
