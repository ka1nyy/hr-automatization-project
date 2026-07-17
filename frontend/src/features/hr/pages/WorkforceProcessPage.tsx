import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, BriefcaseBusiness, CalendarCheck2, FileSignature, Plus, RefreshCw, UserMinus } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader, Section } from '../../../shared/components';
import { formatDate } from '../../../shared/format';
import { useDeveloperStore } from '../../../shared/store';
import { hrRepository } from '../api';
import {
  canActOnProcess,
  listWorkforceProcesses,
  processStatusLabels,
  workforceProcessesApi,
  type LeaveProcess,
  type ProcessKind,
  type TerminationProcess,
  type TripProcess,
  type WorkforceProcess
} from '../api/workforceProcesses';

const config = {
  leave: { eyebrow: 'HR · Отсутствия', title: 'Отпуска', description: 'Заявление, решение руководителя, проверка HR и регистрация в календаре.', icon: CalendarCheck2 },
  trip: { eyebrow: 'HR · Командировки', title: 'Командировки', description: 'Заявка, согласование руководителя, финансов и регистрация HR.', icon: BriefcaseBusiness },
  termination: { eyebrow: 'HR · Кадровые движения', title: 'Увольнения', description: 'Формальный маршрут от HR-проверки до приказа и завершения офбординга.', icon: UserMinus }
} as const;

const pathByKind: Record<ProcessKind, string> = { leave: '/hr/leave', trip: '/hr/business-trips', termination: '/hr/terminations' };
const hrPersonas = ['hr-specialist', 'hr-initiator', 'hr-director'];
const leaveTypeLabels: Record<string, string> = { annual_paid: 'Ежегодный оплачиваемый отпуск', unpaid: 'Отпуск без сохранения заработной платы' };
const terminationReasonLabels: Record<string, string> = { contract_expiry: 'Истечение срока договора', employee_request: 'По инициативе сотрудника', employer_initiative: 'По инициативе работодателя', agreement: 'По соглашению сторон' };

function dateOf(item: WorkforceProcess, kind: ProcessKind) {
  return kind === 'termination' ? (item as TerminationProcess).requested_date : (item as LeaveProcess | TripProcess).start_date;
}

function ProcessCreateForm({ kind, close }: { kind: ProcessKind; close: () => void }) {
  const client = useQueryClient();
  const employees = useQuery({ queryKey: ['hr', 'employees'], queryFn: () => hrRepository.listEmployees() });
  const current = useQuery({ queryKey: ['workforce-process', 'current-employee'], queryFn: workforceProcessesApi.currentEmployee, enabled: kind !== 'termination' });
  const leaveTypes = useQuery({ queryKey: ['workforce-process', 'leave-types'], queryFn: workforceProcessesApi.listLeaveTypes, enabled: kind === 'leave' });
  const leaveBalances = useQuery({ queryKey: ['workforce-process', 'leave-balances'], queryFn: () => workforceProcessesApi.listLeaveBalances(), enabled: kind === 'leave' });
  const reasons = useQuery({ queryKey: ['workforce-process', 'termination-reasons'], queryFn: workforceProcessesApi.listTerminationReasons, enabled: kind === 'termination' });
  const [values, setValues] = useState({ employeeId: '', leaveTypeId: '', startDate: '', endDate: '', reason: '', destination: '', purpose: '', estimatedCost: '0', currency: 'KZT', fundingSource: '', costCenter: '', reasonId: '', requestedDate: '', legalBasis: '' });
  const set = (key: keyof typeof values, value: string) => setValues((currentValues) => ({ ...currentValues, [key]: value }));
  const mutation = useMutation({
    mutationFn: async () => {
      if (kind === 'leave') {
        if (!current.data?.id) throw new Error('Не удалось определить сотрудника текущего аккаунта.');
        return workforceProcessesApi.createLeave({ employeeId: current.data.id, leaveTypeId: values.leaveTypeId, startDate: values.startDate, endDate: values.endDate, reason: values.reason });
      }
      if (kind === 'trip') {
        if (!current.data?.id) throw new Error('Не удалось определить сотрудника текущего аккаунта.');
        return workforceProcessesApi.createTrip({ employeeId: current.data.id, destination: values.destination, startDate: values.startDate, endDate: values.endDate, purpose: values.purpose, estimatedCost: Number(values.estimatedCost), currency: values.currency, fundingDetails: { source: values.fundingSource, costCenter: values.costCenter } });
      }
      const employee = employees.data?.find((item) => item.id === values.employeeId);
      if (!employee?.unitId) throw new Error('У сотрудника отсутствует активное подразделение.');
      return workforceProcessesApi.createTermination({ employeeId: employee.id, unitId: employee.unitId, reasonId: values.reasonId, requestedDate: values.requestedDate, legalBasis: values.legalBasis });
    },
    onSuccess: async () => { await Promise.all([client.invalidateQueries({ queryKey: ['workforce-processes', kind] }), client.invalidateQueries({ queryKey: ['hr'] }), client.invalidateQueries({ queryKey: ['employee-absences'] })]); close(); }
  });
  const submit = (event: FormEvent) => { event.preventDefault(); mutation.mutate(); };
  const balance = leaveBalances.data?.find((item) => item.leave_type_id === values.leaveTypeId);
  const availableDays = balance ? balance.entitlement_days - balance.used_days - balance.reserved_days : null;
  return <Section className="workforce-create-section" title={kind === 'termination' ? 'Запустить увольнение' : kind === 'leave' ? 'Новая заявка на отпуск' : 'Новая командировка'} meta="Данные сохраняются в кадровом контуре">
    <form onSubmit={submit} className="field-grid workforce-create-form">
      {kind === 'termination' && <>
        <label className="span-two">Сотрудник<select required value={values.employeeId} onChange={(event) => set('employeeId', event.target.value)}><option value="">Выберите сотрудника</option>{(employees.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.fullName} · {item.position}</option>)}</select></label>
        <label className="span-two">Причина<select required value={values.reasonId} onChange={(event) => set('reasonId', event.target.value)}><option value="">Выберите основание</option>{(reasons.data ?? []).map((item) => <option key={item.id} value={item.id}>{terminationReasonLabels[item.code] ?? item.name}</option>)}</select></label>
        <label>Желаемая дата<input required min={new Date().toISOString().slice(0, 10)} type="date" value={values.requestedDate} onChange={(event) => set('requestedDate', event.target.value)} /></label>
        <label className="span-two">Правовое основание<textarea required rows={3} value={values.legalBasis} onChange={(event) => set('legalBasis', event.target.value)} placeholder="Статья ТК РК, заявление или соглашение" /></label>
      </>}
      {kind === 'leave' && <>
        <label className="span-two">Тип отпуска<select required value={values.leaveTypeId} onChange={(event) => set('leaveTypeId', event.target.value)}><option value="">Выберите тип</option>{(leaveTypes.data ?? []).map((item) => <option key={item.id} value={item.id}>{leaveTypeLabels[item.code] ?? item.name}</option>)}</select></label>
        {availableDays !== null && <div className="leave-balance-inline span-two"><CalendarCheck2 size={18} /><span><small>Доступно по выбранному типу</small><strong>{availableDays} дней</strong></span></div>}
        <label>Дата начала<input required min={new Date().toISOString().slice(0, 10)} type="date" value={values.startDate} onChange={(event) => set('startDate', event.target.value)} /></label>
        <label>Дата окончания<input required min={values.startDate || new Date().toISOString().slice(0, 10)} type="date" value={values.endDate} onChange={(event) => set('endDate', event.target.value)} /></label>
        <label className="span-two">Комментарий<textarea rows={3} value={values.reason} onChange={(event) => set('reason', event.target.value)} /></label>
      </>}
      {kind === 'trip' && <>
        <label className="span-two">Место назначения<input required value={values.destination} onChange={(event) => set('destination', event.target.value)} placeholder="Город, страна" /></label>
        <label>Дата начала<input required min={new Date().toISOString().slice(0, 10)} type="date" value={values.startDate} onChange={(event) => set('startDate', event.target.value)} /></label>
        <label>Дата окончания<input required min={values.startDate || new Date().toISOString().slice(0, 10)} type="date" value={values.endDate} onChange={(event) => set('endDate', event.target.value)} /></label>
        <label className="span-two">Цель командировки<textarea required rows={3} value={values.purpose} onChange={(event) => set('purpose', event.target.value)} /></label>
        <label>Бюджет<input required type="number" min="0" value={values.estimatedCost} onChange={(event) => set('estimatedCost', event.target.value)} /></label>
        <label>Валюта<select value={values.currency} onChange={(event) => set('currency', event.target.value)}><option>KZT</option><option>USD</option><option>EUR</option></select></label>
        <label>Источник финансирования<input value={values.fundingSource} onChange={(event) => set('fundingSource', event.target.value)} placeholder="Бюджет подразделения" /></label>
        <label>Центр затрат<input value={values.costCenter} onChange={(event) => set('costCenter', event.target.value)} placeholder="Например, HR-101" /></label>
      </>}
      {mutation.error && <div className="api-error-card span-two"><strong>Не удалось отправить</strong><p>{mutation.error.message}</p></div>}
      <div className="hr-form-footer span-two"><button type="button" className="secondary-button" onClick={close}>Отмена</button><button className="primary-button" disabled={mutation.isPending}><FileSignature size={16} />{mutation.isPending ? 'Отправка…' : 'Запустить маршрут'}</button></div>
    </form>
  </Section>;
}

export default function WorkforceProcessPage({ kind }: { kind: ProcessKind }) {
  const persona = useDeveloperStore((state) => state.persona);
  const locale = useDeveloperStore((state) => state.locale);
  const [creating, setCreating] = useState(false);
  const definition = config[kind];
  const query = useQuery({
    queryKey: ['workforce-processes', kind, persona],
    queryFn: () => listWorkforceProcesses(kind)
  });
  const employees = useQuery({ queryKey: ['hr', 'employees'], queryFn: () => hrRepository.listEmployees() });
  const rows = query.data ?? [];
  const employeeNames = new Map((employees.data ?? []).map((item) => [item.id, item.fullName]));
  const actionable = rows.filter((item) => canActOnProcess(persona, kind, item.status)).length;
  const completed = rows.filter((item) => ['approved', 'registered', 'completed'].includes(item.status)).length;
  const canCreate = kind === 'termination' ? hrPersonas.includes(persona) : persona === 'employee';
  const Icon = definition.icon;

  return <>
    <PageHeader eyebrow={definition.eyebrow} title={definition.title} description={definition.description} actions={<>{canCreate && <button className="primary-button" onClick={() => setCreating(!creating)}><Plus size={16} />{kind === 'termination' ? 'Начать увольнение' : 'Создать заявку'}</button>}</>} />
    {creating && <ProcessCreateForm kind={kind} close={() => setCreating(false)} />}
    <div className="planned-metric-grid">
      <article><span><Icon size={20} /></span><div><small>Всего записей</small><strong>{rows.length}</strong><em>из backend</em></div></article>
      <article><span><FileSignature size={20} /></span><div><small>Требуют действия</small><strong>{actionable}</strong><em>для текущей роли</em></div></article>
      <article><span><CalendarCheck2 size={20} /></span><div><small>Завершено</small><strong>{completed}</strong><em>маршрут пройден</em></div></article>
    </div>
    <div className="hiring-list-toolbar"><span><Icon size={17} />{rows.length} записей</span><button className="secondary-button" onClick={() => void query.refetch()}><RefreshCw size={15} />Обновить</button></div>
    {query.isError ? <div className="api-error-card"><strong>Не удалось загрузить данные</strong><p>{query.error instanceof Error ? query.error.message : 'Ошибка API'}</p></div> : query.isLoading || employees.isLoading ? <div className="hiring-empty">Загрузка…</div> : rows.length ? <div className="hiring-request-list">{rows.map((item) => {
      const leave = kind === 'leave' ? item as LeaveProcess : null;
      const trip = kind === 'trip' ? item as TripProcess : null;
      const title = employeeNames.get(item.employee_id) ?? 'Сотрудник';
      const detail = leave ? `${formatDate(leave.start_date, locale)} — ${formatDate(leave.end_date, locale)} · ${leave.requested_days} дн.` : trip ? `${trip.destination} · ${formatDate(trip.start_date, locale)} — ${formatDate(trip.end_date, locale)}` : `Желаемая дата: ${formatDate((item as TerminationProcess).requested_date, locale)}`;
      return <Link key={item.id} to={`${pathByKind[kind]}/${item.id}`} className="hiring-request-card"><span className="hiring-request-icon"><Icon size={20} /></span><div><small>{kind === 'leave' ? 'ОТПУСК' : kind === 'trip' ? 'КОМАНДИРОВКА' : 'УВОЛЬНЕНИЕ'}</small><strong>{title}</strong><p>{detail}</p></div><span className={`hiring-status ${item.status}`}>{processStatusLabels[item.status] ?? item.status}</span><div className="hiring-request-stage"><small>{canActOnProcess(persona, kind, item.status) ? 'Ожидает вашего решения' : 'Маршрут выполняется'}</small><time>{formatDate(dateOf(item, kind), locale)}</time></div><ArrowRight size={18} /></Link>;
    })}</div> : <div className="hiring-empty"><span><Icon size={28} /></span><strong>Записей пока нет</strong><p>Новые заявки появятся здесь сразу после отправки в backend.</p></div>}
  </>;
}
