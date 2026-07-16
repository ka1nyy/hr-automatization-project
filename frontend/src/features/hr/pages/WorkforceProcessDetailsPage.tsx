import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, FileCheck2, ShieldCheck, Undo2, X } from 'lucide-react';
import { useState } from 'react';
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
  type TripProcess,
  type WorkforceProcess
} from '../api/workforceProcesses';

const pathByKind: Record<ProcessKind, string> = { leave: '/hr/leave', trip: '/hr/business-trips', termination: '/hr/terminations' };
const stages: Record<ProcessKind, Array<{ code: string; name: string }>> = {
  leave: [{ code: 'manager_review', name: 'Руководитель' }, { code: 'hr_review', name: 'HR-проверка' }, { code: 'approved', name: 'Календарь' }],
  trip: [{ code: 'manager_review', name: 'Руководитель' }, { code: 'finance_review', name: 'Финансы' }, { code: 'hr_registration', name: 'HR-регистрация' }, { code: 'registered', name: 'Завершено' }],
  termination: [{ code: 'hr_review', name: 'HR-проверка' }, { code: 'legal_review', name: 'Юридическая проверка' }, { code: 'signature', name: 'Подписание' }, { code: 'registration', name: 'Приказ' }, { code: 'offboarding', name: 'Офбординг' }, { code: 'scheduled', name: 'Запланировано' }, { code: 'completed', name: 'Завершено' }]
};

function Timeline({ kind, status }: { kind: ProcessKind; status: string }) {
  const route = stages[kind];
  const active = route.findIndex((item) => item.code === status);
  const terminal = ['approved', 'registered', 'completed'].includes(status);
  return <ol className="hiring-approval-timeline">{route.map((stage, index) => <li key={stage.code} className={terminal || (active >= 0 && index < active) ? 'approve' : index === active ? 'current' : ''}><span>{terminal || (active >= 0 && index < active) ? <Check size={16} /> : index + 1}</span><div><small>Этап {index + 1}</small><strong>{stage.name}</strong><p>{index === active ? 'Ожидает действия текущей роли' : terminal || (active >= 0 && index < active) ? 'Завершено' : 'Ожидает предыдущий этап'}</p></div></li>)}</ol>;
}

export default function WorkforceProcessDetailsPage({ kind }: { kind: ProcessKind }) {
  const { id = '' } = useParams();
  const persona = useDeveloperStore((state) => state.persona);
  const locale = useDeveloperStore((state) => state.locale);
  const client = useQueryClient();
  const [comment, setComment] = useState('');
  const [documentId, setDocumentId] = useState('');
  const [effectiveDate, setEffectiveDate] = useState('');
  const [error, setError] = useState('');
  const query = useQuery({ queryKey: ['workforce-processes', kind, persona], queryFn: () => listWorkforceProcesses(kind) });
  const employees = useQuery({ queryKey: ['hr', 'employees'], queryFn: () => hrRepository.listEmployees() });
  const item = query.data?.find((row) => row.id === id) as WorkforceProcess | undefined;
  const action = useMutation({
    mutationFn: async (command: ProcessDecision | 'cancel' | 'register-order' | 'schedule' | 'complete') => {
      if (!item) throw new Error('Запись не загружена.');
      if ((command === 'return' || command === 'reject' || command === 'cancel') && !comment.trim()) throw new Error('Укажите причину решения.');
      if (command === 'cancel') return kind === 'leave' ? workforceProcessesApi.cancelLeave(item as LeaveProcess, comment) : workforceProcessesApi.cancelTrip(item as TripProcess, comment);
      if (command === 'register-order') return workforceProcessesApi.registerTerminationOrder(item as TerminationProcess, documentId);
      if (command === 'schedule') return workforceProcessesApi.scheduleTermination(item as TerminationProcess, effectiveDate);
      if (command === 'complete') return workforceProcessesApi.completeTermination(item as TerminationProcess);
      if (kind === 'leave') return workforceProcessesApi.decideLeave(item as LeaveProcess, command, comment);
      if (kind === 'trip') return workforceProcessesApi.decideTrip(item as TripProcess, command, comment);
      return workforceProcessesApi.decideTermination(item as TerminationProcess, command, comment);
    },
    onSuccess: async () => { setComment(''); setError(''); await client.invalidateQueries({ queryKey: ['workforce-processes', kind] }); },
    onError: (value) => setError(value instanceof Error ? value.message : 'Действие не выполнено')
  });
  if (query.isLoading || employees.isLoading) return <div className="hiring-empty">Загрузка…</div>;
  if (!item) return <div className="api-error-card"><strong>Запись не найдена</strong><p>{query.error instanceof Error ? query.error.message : 'Проверьте доступ текущей роли.'}</p></div>;

  const employee = employees.data?.find((person) => person.id === item.employee_id);
  const canAct = canActOnProcess(persona, kind, item.status);
  const reviewStage = kind !== 'termination' || ['hr_review', 'legal_review', 'signature'].includes(item.status);
  const leave = kind === 'leave' ? item as LeaveProcess : null;
  const trip = kind === 'trip' ? item as TripProcess : null;
  const termination = kind === 'termination' ? item as TerminationProcess : null;
  const subtitle = leave ? `${formatDate(leave.start_date, locale)} — ${formatDate(leave.end_date, locale)} · ${leave.requested_days} дней` : trip ? `${trip.destination} · ${formatDate(trip.start_date, locale)} — ${formatDate(trip.end_date, locale)}` : `Желаемая дата увольнения: ${formatDate(termination!.requested_date, locale)}`;

  return <>
    <PageHeader eyebrow={kind === 'leave' ? 'Заявка на отпуск' : kind === 'trip' ? 'Заявка на командировку' : 'Маршрут увольнения'} title={employee?.fullName ?? 'Сотрудник'} description={subtitle} actions={<Link className="secondary-button" to={pathByKind[kind]}>Назад к очереди</Link>} />
    {error && <div className="api-error-card"><strong>Действие не выполнено</strong><p>{error}</p></div>}
    <div className="hiring-detail-grid">
      <section className="hiring-detail-main"><header><span><ShieldCheck size={20} /></span><div><small>Текущий статус</small><strong>{processStatusLabels[item.status] ?? item.status}</strong></div></header>
        <div className="hiring-summary-grid"><dl><dt>Сотрудник</dt><dd>{employee?.fullName ?? item.employee_id}</dd></dl><dl><dt>Подразделение</dt><dd>{employee?.department ?? '—'}</dd></dl>{trip && <><dl><dt>Бюджет</dt><dd>{trip.estimated_cost} {trip.currency}</dd></dl><dl><dt>Цель</dt><dd>{trip.purpose}</dd></dl></>}{leave && <dl><dt>Комментарий</dt><dd>{leave.reason || '—'}</dd></dl>}{termination && <dl><dt>Дата</dt><dd>{termination.effective_date ? formatDate(termination.effective_date, locale) : formatDate(termination.requested_date, locale)}</dd></dl>}</div>
        <h3>Маршрут процесса</h3><Timeline kind={kind} status={item.status} />
      </section>
      <aside className="hiring-document-panel"><h3><FileCheck2 size={18} />Действия</h3>
        {canAct && reviewStage && <div className="hiring-action-box"><label>Комментарий<textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Комментарий к решению" /></label><div><button className="success-button" disabled={action.isPending} onClick={() => action.mutate('approve')}><Check size={16} />Согласовать</button><button className="secondary-button" disabled={action.isPending} onClick={() => action.mutate('return')}><Undo2 size={16} />Вернуть</button><button className="danger-button" disabled={action.isPending} onClick={() => action.mutate('reject')}><X size={16} />Отклонить</button></div></div>}
        {canAct && kind === 'termination' && item.status === 'registration' && <div className="hiring-action-box"><label>ID зарегистрированного приказа<input value={documentId} onChange={(event) => setDocumentId(event.target.value)} placeholder="UUID документа" /></label><button className="primary-button full" disabled={!documentId || action.isPending} onClick={() => action.mutate('register-order')}>Зарегистрировать приказ</button></div>}
        {canAct && kind === 'termination' && item.status === 'offboarding' && <div className="hiring-action-box"><label>Дата увольнения<input type="date" value={effectiveDate} onChange={(event) => setEffectiveDate(event.target.value)} /></label><button className="primary-button full" disabled={!effectiveDate || action.isPending} onClick={() => action.mutate('schedule')}>Запланировать завершение</button><small>Перед финальным завершением backend проверит приказ, документы и задачи офбординга.</small></div>}
        {canAct && kind === 'termination' && ['scheduled', 'effective'].includes(item.status) && <button className="primary-button full" disabled={action.isPending} onClick={() => action.mutate('complete')}>Завершить увольнение</button>}
        {persona === 'employee' && kind !== 'termination' && !['cancelled', 'rejected'].includes(item.status) && <div className="hiring-action-box"><label>Причина отмены<textarea value={comment} onChange={(event) => setComment(event.target.value)} /></label><button className="danger-button full" disabled={action.isPending} onClick={() => action.mutate('cancel')}>Отменить заявку</button></div>}
        {!canAct && persona !== 'employee' && <div className="hiring-empty"><strong>Нет действий на этом этапе</strong><p>Запись автоматически появится у следующей роли после решения текущего согласующего.</p></div>}
      </aside>
    </div>
  </>;
}
