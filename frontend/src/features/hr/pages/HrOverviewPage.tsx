import { useQuery } from '@tanstack/react-query';
import { ArrowRight, ArrowUpRight, CalendarCheck2, CheckCircle2, Clock3, FileWarning, GraduationCap, Inbox, ListTodo, ShieldCheck, UserCheck, UserPlus, UsersRound } from 'lucide-react';
import { Link } from 'react-router-dom';
import { repositories } from '../../../repositories';
import { PageHeader, QueryState, Section } from '../../../shared/components';
import { BarChart, DonutChart } from '../../../shared/charts';
import { formatDate, statusLabels } from '../../../shared/format';
import { usePermission } from '../../../shared/permissions';
import { useDeveloperStore } from '../../../shared/store';
import { hrRepository } from '../api';
import { LeaveStatus } from '../components/HrStatus';

export default function HrOverviewPage() {
  const persona = useDeveloperStore((state) => state.persona);
  const locale = useDeveloperStore((state) => state.locale);
  const canOpen = usePermission('hr.read');
  const isHr = persona === 'hr-specialist';
  const overview = useQuery({ queryKey: ['hr', 'overview'], queryFn: () => hrRepository.getOverview(), enabled: canOpen && isHr });
  const employee = useQuery({ queryKey: ['hr', 'employee', 'me'], queryFn: () => hrRepository.getCurrentEmployee(), enabled: canOpen && !isHr });
  const leaveRequests = useQuery({ queryKey: ['hr', 'leave'], queryFn: () => hrRepository.listLeaveRequests(), enabled: canOpen });
  const messages = useQuery({ queryKey: ['incoming'], queryFn: () => repositories.correspondence.listIncoming(), enabled: canOpen && isHr });
  const tasks = useQuery({ queryKey: ['tasks'], queryFn: () => repositories.tasks.list(), enabled: canOpen && isHr });

  if (!canOpen) return <div className="hr-access-denied"><span>HR</span><h1>Рабочее пространство недоступно</h1><p>Выбранная роль не участвует в HR self-service или кадровых процессах.</p><Link className="secondary-button" to="/">На главную</Link></div>;
  if (overview.isLoading || employee.isLoading || leaveRequests.isLoading || messages.isLoading || tasks.isLoading) return <QueryState />;
  const error = overview.error || employee.error || leaveRequests.error || messages.error || tasks.error;
  if (error) return <QueryState error={error} retry={() => { overview.refetch(); employee.refetch(); leaveRequests.refetch(); messages.refetch(); tasks.refetch(); }} />;

  if (!isHr) {
    const person = employee.data!;
    const ownRequests = leaveRequests.data!.filter((item) => item.employeeId === person.id);
    return <>
      <PageHeader eyebrow="HR · Сотрудник" title={`Здравствуйте, ${person.fullName.split(' ')[0]}`} actions={<Link className="primary-button" to="/hr/leave"><CalendarCheck2 size={16} /> Новая заявка</Link>} />
      <div className="hr-employee-hero">
        <div className="hr-person"><span className="avatar hr-avatar-xl">{person.initials}</span><div><strong>{person.fullName}</strong><span>{person.position} · {person.department}</span><small>{person.employeeNumber}</small></div></div>
        <div className="hr-balance"><span>Доступный отпуск</span><strong>{person.leaveBalance}<small>дней</small></strong><i><b style={{ width: `${Math.min(100, person.leaveBalance / 28 * 100)}%` }} /></i></div>
        <div className="hr-file-score"><span>Личное дело</span><strong>{person.personnelFileCompleteness}%</strong><small>{person.personnelFileCompleteness < 100 ? 'Нужно дополнить документы' : 'Все документы на месте'}</small></div>
      </div>
      <div className="hr-dashboard-grid employee-view">
        <Section title="Мои заявки" meta={`${ownRequests.length} активных`}><div className="hr-request-list">{ownRequests.map((request) => <article key={request.id}><span className="hr-list-icon"><CalendarCheck2 size={17} /></span><div><strong>{request.leaveType}</strong><small>{formatDate(request.startDate, locale, 'dd MMM')} — {formatDate(request.endDate, locale, 'dd MMM yyyy')} · {request.days} дней</small></div><LeaveStatus status={request.status} /></article>)}</div><Link className="panel-link" to="/hr/leave">Открыть заявки <ArrowRight size={15} /></Link></Section>
        <Section title="Ближайшие события"><div className="hr-event-list"><div><span className="tone-violet"><GraduationCap size={17} /></span><div><strong>Оценка KPI за II квартал</strong><small>Заполнить самооценку до 20 июля</small></div></div><div><span className="tone-teal"><UserCheck size={17} /></span><div><strong>One-to-one с руководителем</strong><small>22 июля · 15:00</small></div></div><div><span className="tone-gold"><FileWarning size={17} /></span><div><strong>Обновить контактные данные</strong><small>Профиль заполнен на 92%</small></div></div></div></Section>
      </div>
    </>;
  }

  const stats = overview.data!;
  const pending = leaveRequests.data!.filter((item) => item.status === 'hr_review');
  const activeTasks = tasks.data!.filter((task) => task.state !== 'completed');
  const workforceTotal = Math.max(1, stats.activeEmployees + stats.onLeave + stats.onBusinessTrip + stats.onSickLeave);
  const presenceRate = Math.round(stats.activeEmployees / workforceTotal * 100);
  const workforceChart = [
    { label: 'Активны', value: stats.activeEmployees, color: 'var(--teal)', detail: 'На рабочем месте', to: '/hr/employees' },
    { label: 'В отпуске', value: stats.onLeave, color: 'var(--gold)', detail: 'Плановое отсутствие', to: '/hr/leave' },
    { label: 'Командировка', value: stats.onBusinessTrip, color: 'var(--violet)', detail: 'Служебная поездка', to: '/hr/calendar' },
    { label: 'Больничный', value: stats.onSickLeave, color: 'var(--coral)', detail: 'Нетрудоспособность', to: '/hr/sick-leave' },
  ];
  const controlChart = [
    { label: 'Процессы', value: stats.activeProcesses, color: 'var(--teal)', to: '/processes' },
    { label: 'Дела < 90%', value: stats.incompleteFiles, color: 'var(--gold)', to: '/hr/documents' },
    { label: 'Договоры', value: stats.expiringContracts, color: 'var(--violet)', to: '/hr/employees?query=2026' },
    { label: 'Просрочено', value: stats.overdueTasks, color: 'var(--coral)', to: '/tasks?filter=overdue' },
  ];
  const urgentMessages = messages.data!.filter((item) => item.priority === 'urgent').length;
  const overdueTasks = activeTasks.filter((task) => task.state === 'overdue').length;

  return <>
    <PageHeader eyebrow="HR · Главная" title="Рабочее пространство" actions={<><Link className="secondary-button" to="/hr/employees"><UsersRound size={16} /> Сотрудники</Link><Link className="primary-button" to="/hr/employees?add=true"><UserPlus size={16} /> Добавить сотрудника</Link></>} />
    
    <div className="dashboard-chart-grid hr-dashboard-charts">
      <Section title="Структура присутствия" meta={`${workforceTotal} сотрудников`}><DonutChart data={workforceChart} centerValue={`${presenceRate}%`} centerLabel="активны" ariaLabel="Распределение сотрудников по типу присутствия" /></Section>
      <Section title="HR-контроль" meta="Актуальные риски"><BarChart data={controlChart} ariaLabel="HR-показатели, требующие контроля" /></Section>
    </div>

    <section className="admin-command-center" aria-labelledby="admin-command-title">
      <header><div><span>ADMIN COMMAND CENTER</span><h2 id="admin-command-title">Что требует вашего внимания</h2><p>Двигайтесь слева направо: прочитайте новое, выполните задачи, примите решения.</p></div><span className="admin-live"><i /> Данные актуальны</span></header>

      <div className="admin-command-summary">
        <Link to="/correspondence/incoming" className="summary-blue"><span><Inbox size={21} /></span><div><small>1. Разобрать входящие</small><strong>{messages.data!.length}<em>сообщений</em></strong><p>{urgentMessages ? `${urgentMessages} срочных — начните с них` : 'Срочных сообщений нет'}</p></div><ArrowUpRight size={18} /></Link>
        <Link to="/tasks" className="summary-violet"><span><ListTodo size={21} /></span><div><small>2. Выполнить задачи</small><strong>{activeTasks.length}<em>в работе</em></strong><p>{overdueTasks ? `${overdueTasks} просрочено — требуют действия` : 'Все задачи в плановом сроке'}</p></div><ArrowUpRight size={18} /></Link>
        <Link to="/hr/approvals" className="summary-amber"><span><ShieldCheck size={21} /></span><div><small>3. Принять решения</small><strong>{pending.length}<em>ожидают HR</em></strong><p>{pending.length ? 'Проверьте даты и замещение' : 'Все решения приняты'}</p></div><ArrowUpRight size={18} /></Link>
      </div>

      <div className="admin-queue-board">
        <section className="admin-queue queue-inbox"><header><span><Inbox size={18} /></span><div><h3>Входящие</h3><small>Новая информация и запросы</small></div><b>{messages.data!.length}</b></header><div className="admin-queue-list">{messages.data!.slice(0, 3).map((item) => <Link to={`/correspondence/incoming/${item.id}`} className="admin-queue-card" key={item.id}><div className="admin-card-top"><span className={`admin-priority priority-${item.priority}`}>{item.priority === 'urgent' ? 'Срочно' : item.priority === 'high' ? 'Важно' : 'Обычно'}</span><time><Clock3 size={12} />до {formatDate(item.dueDate, locale, 'dd MMM')}</time></div><strong>{item.subject}</strong><p>{item.sender}</p><footer><span><i className={`status-dot status-${item.status}`} />{statusLabels[item.status]}</span><b>Открыть <ArrowRight size={14} /></b></footer></Link>)}</div><Link className="admin-queue-footer" to="/correspondence/incoming">Все входящие <ArrowRight size={15} /></Link></section>

        <section className="admin-queue queue-tasks"><header><span><ListTodo size={18} /></span><div><h3>Задачи</h3><small>То, что нужно сделать</small></div><b>{activeTasks.length}</b></header><div className="admin-queue-list">{activeTasks.slice(0, 3).map((task) => <Link to="/tasks" className="admin-queue-card" key={task.id}><div className="admin-card-top"><span className={`admin-priority priority-${task.priority}`}>{task.state === 'overdue' ? 'Просрочено' : task.priority === 'urgent' ? 'Срочно' : 'В работе'}</span><time><Clock3 size={12} />до {formatDate(task.dueDate, locale, 'dd MMM')}</time></div><strong>{task.title}</strong><p>{task.process} · {task.documentNumber}</p><footer><span>{task.assignee ? `Исполнитель: ${task.assignee}` : 'Не назначено'}</span><b>К задаче <ArrowRight size={14} /></b></footer></Link>)}</div><Link className="admin-queue-footer" to="/tasks">Все задачи <ArrowRight size={15} /></Link></section>

        <section className="admin-queue queue-approvals"><header><span><ShieldCheck size={18} /></span><div><h3>Согласования</h3><small>Там, где нужно решение HR</small></div><b>{pending.length}</b></header><div className="admin-queue-list">{pending.length ? pending.slice(0, 3).map((request) => <Link to="/hr/approvals" className="admin-queue-card approval-card" key={request.id}><div className="admin-card-top"><LeaveStatus status={request.status} /><time>{request.days} дней</time></div><strong>{request.employeeName}</strong><p>{request.leaveType} · {formatDate(request.startDate, locale, 'dd MMM')} — {formatDate(request.endDate, locale, 'dd MMM')}</p><div className="approval-route" aria-label="Этапы согласования"><span className="done"><CheckCircle2 size={13} />Руководитель</span><i /><span className="active">2. HR</span><i /><span>3. Приказ</span></div><footer><span>{request.documentNumber}</span><b>Рассмотреть <ArrowRight size={14} /></b></footer></Link>) : <div className="admin-queue-empty"><span><CheckCircle2 size={24} /></span><strong>Всё согласовано</strong><p>Новых решений для HR нет.</p></div>}</div><Link className="admin-queue-footer" to="/hr/approvals">Все согласования <ArrowRight size={15} /></Link></section>
      </div>
    </section>
  </>;
}
