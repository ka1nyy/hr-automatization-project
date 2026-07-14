import { useQuery } from '@tanstack/react-query';
import { AlertCircle, ArrowRight, BriefcaseBusiness, CalendarCheck2, Clock3, FileWarning, GraduationCap, UserCheck, UsersRound } from 'lucide-react';
import { Link } from 'react-router-dom';
import { PageHeader, QueryState, Section } from '../../../shared/components';
import { formatDate } from '../../../shared/format';
import { usePermission } from '../../../shared/permissions';
import { useDeveloperStore } from '../../../shared/store';
import { hrRepository } from '../api';
import { HrSubnav } from '../components/HrSubnav';
import { LeaveStatus } from '../components/HrStatus';

export default function HrOverviewPage() {
  const persona = useDeveloperStore((state) => state.persona);
  const locale = useDeveloperStore((state) => state.locale);
  const canOpen = usePermission('hr.read');
  const isHr = persona === 'hr-specialist';
  const overview = useQuery({ queryKey: ['hr', 'overview'], queryFn: () => hrRepository.getOverview(), enabled: canOpen && isHr });
  const employee = useQuery({ queryKey: ['hr', 'employee', 'e-3'], queryFn: () => hrRepository.getEmployee('e-3'), enabled: canOpen && !isHr });
  const leaveRequests = useQuery({ queryKey: ['hr', 'leave'], queryFn: () => hrRepository.listLeaveRequests(), enabled: canOpen });
  if (!canOpen) return <div className="hr-access-denied"><span>HR</span><h1>Рабочее пространство недоступно</h1><p>Выбранная роль не участвует в HR self-service или кадровых процессах.</p><Link className="secondary-button" to="/">На главную</Link></div>;
  if (overview.isLoading || employee.isLoading || leaveRequests.isLoading) return <QueryState />;
  const error = overview.error || employee.error || leaveRequests.error;
  if (error) return <QueryState error={error} retry={() => { overview.refetch(); employee.refetch(); leaveRequests.refetch(); }} />;

  if (!isHr) {
    const person = employee.data!;
    const ownRequests = leaveRequests.data!.filter((item) => item.employeeId === person.id);
    return <>
      <HrSubnav />
      <PageHeader eyebrow="HR пространство · Сотрудник" title={`Здравствуйте, ${person.fullName.split(' ')[0]}`} description="Личные кадровые данные, заявки и ближайшие события в одном месте." actions={<Link className="primary-button" to="/departments/hr/leave"><CalendarCheck2 size={16} /> Новая заявка</Link>} />
      <div className="hr-employee-hero">
        <div className="hr-person"><span className="avatar hr-avatar-xl">{person.initials}</span><div><strong>{person.fullName}</strong><span>{person.position} · {person.department}</span><small>{person.employeeNumber}</small></div></div>
        <div className="hr-balance"><span>Доступный отпуск</span><strong>{person.leaveBalance}<small>дней</small></strong><i><b style={{ width: `${Math.min(100, person.leaveBalance / 28 * 100)}%` }} /></i></div>
        <div className="hr-file-score"><span>Личное дело</span><strong>{person.personnelFileCompleteness}%</strong><small>{person.personnelFileCompleteness < 100 ? 'Нужно дополнить документы' : 'Все документы на месте'}</small></div>
      </div>
      <div className="hr-dashboard-grid employee-view">
        <Section title="Мои заявки" meta={`${ownRequests.length} активных`}><div className="hr-request-list">{ownRequests.map((request) => <article key={request.id}><span className="hr-list-icon"><CalendarCheck2 size={17} /></span><div><strong>{request.leaveType}</strong><small>{formatDate(request.startDate, locale, 'dd MMM')} — {formatDate(request.endDate, locale, 'dd MMM yyyy')} · {request.days} дней</small></div><LeaveStatus status={request.status} /></article>)}</div><Link className="panel-link" to="/departments/hr/leave">Открыть заявки <ArrowRight size={15} /></Link></Section>
        <Section title="Ближайшие события"><div className="hr-event-list"><div><span className="tone-violet"><GraduationCap size={17} /></span><div><strong>Оценка KPI за II квартал</strong><small>Заполнить самооценку до 20 июля</small></div></div><div><span className="tone-teal"><UserCheck size={17} /></span><div><strong>One-to-one с руководителем</strong><small>22 июля · 15:00</small></div></div><div><span className="tone-gold"><FileWarning size={17} /></span><div><strong>Обновить контактные данные</strong><small>Профиль заполнен на 92%</small></div></div></div></Section>
      </div>
    </>;
  }

  const stats = overview.data!;
  const pending = leaveRequests.data!.filter((item) => item.status === 'hr_review');
  return <>
    <HrSubnav />
    <PageHeader eyebrow="Департамент управления персоналом" title="HR Operations" description="Состояние персонала, кадровых процессов и задач на текущий день." actions={<Link className="secondary-button" to="/departments/hr/employees"><UsersRound size={16} /> Каталог сотрудников</Link>} />
    <div className="hr-metric-grid">
      <article><span className="tone-teal"><UsersRound size={18} /></span><div><small>Активные сотрудники</small><strong>{stats.activeEmployees}</strong><em>+4 с начала месяца</em></div></article>
      <article><span className="tone-violet"><UserCheck size={18} /></span><div><small>На испытательном</small><strong>{stats.onProbation}</strong><em>5 сроков в июле</em></div></article>
      <article><span className="tone-gold"><CalendarCheck2 size={18} /></span><div><small>Сейчас в отпуске</small><strong>{stats.onLeave}</strong><em>8% штата</em></div></article>
      <article><span className="tone-emerald"><BriefcaseBusiness size={18} /></span><div><small>Открытые вакансии</small><strong>{stats.openVacancies}</strong><em>38 кандидатов</em></div></article>
      <article><span className="tone-coral"><Clock3 size={18} /></span><div><small>Просрочено задач</small><strong>{stats.overdueTasks}</strong><em>Требуют внимания</em></div></article>
      <article><span className="tone-gold"><FileWarning size={18} /></span><div><small>Неполные дела</small><strong>{stats.incompleteFiles}</strong><em>{stats.expiringContracts} договоров истекают</em></div></article>
    </div>
    <div className="hr-dashboard-grid">
      <Section title="Заявки на проверку" meta={`${pending.length} ожидают HR`}><div className="hr-request-list">{pending.length ? pending.map((request) => <article key={request.id}><span className="hr-list-icon"><CalendarCheck2 size={17} /></span><div><strong>{request.employeeName}</strong><small>{request.leaveType} · {request.days} дней · {request.documentNumber}</small></div><LeaveStatus status={request.status} /></article>) : <div className="hr-inline-empty">Очередь проверки пуста</div>}</div><Link className="panel-link" to="/departments/hr/leave">Вся очередь <ArrowRight size={15} /></Link></Section>
      <Section title="Фокус HR на сегодня"><div className="hr-focus-list"><div><b className="tone-coral">04</b><span><strong>Просроченные задачи</strong><small>Onboarding и кадровые документы</small></span></div><div><b className="tone-gold">07</b><span><strong>Онбординг в работе</strong><small>2 сотрудника выходят на этой неделе</small></span></div><div><b className="tone-violet">05</b><span><strong>Испытательные сроки</strong><small>Ожидают итоговой оценки</small></span></div></div></Section>
      <Section title="Распределение персонала" meta="180 сотрудников"><div className="hr-workforce"><div style={{ '--share': '24%' } as React.CSSProperties}><span>Инвестиции</span><i><b /></i><strong>43</strong></div><div style={{ '--share': '20%' } as React.CSSProperties}><span>Активы</span><i><b /></i><strong>36</strong></div><div style={{ '--share': '17%' } as React.CSSProperties}><span>Строительство</span><i><b /></i><strong>31</strong></div><div style={{ '--share': '14%' } as React.CSSProperties}><span>Экономика</span><i><b /></i><strong>25</strong></div><div style={{ '--share': '11%' } as React.CSSProperties}><span>Юридический</span><i><b /></i><strong>20</strong></div></div></Section>
      <Section title="Состояние процессов"><div className="hr-process-health"><div><span className="tone-emerald"><i /></span><strong>94%</strong><small>HR SLA в норме</small></div><div><span className="tone-gold"><i /></span><strong>12</strong><small>На согласовании</small></div><div><span className="tone-coral"><AlertCircle size={16} /></span><strong>1</strong><small>Инцидент workflow</small></div></div></Section>
    </div>
  </>;
}
