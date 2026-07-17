import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Calendar, CalendarCheck2, CheckCircle2, FileWarning, GraduationCap, Inbox, MapPin, ShieldCheck, UserCheck, UsersRound, Video } from 'lucide-react';
import { Link } from 'react-router-dom';
import { PageHeader, QueryState, Section } from '../../../shared/components';
import { DonutChart } from '../../../shared/charts';
import { formatDate } from '../../../shared/format';
import { getPermissions, usePermission } from '../../../shared/permissions';
import { useDeveloperStore } from '../../../shared/store';
import { UNIFIED_HR_WORKSPACE } from '../../../shared/unifiedHrWorkspace';
import { hrRepository } from '../api';
import { hiringRequestsApi, hiringStatusLabels, type HiringRequestScope } from '../api/hiringRequests';
import { LeaveStatus } from '../components/HrStatus';

const mockMeetings = [
  { id: '1', title: 'Интервью: Смагулов Р. Э.', time: '11:30', date: 'Сегодня', type: 'online', location: 'Google Meet', badge: 'IT-Специалист' },
  { id: '2', title: 'Синхронизация HR-департамента', time: '14:00', date: 'Сегодня', type: 'offline', location: 'Переговорная «Астана»', badge: 'Внутреннее' },
  { id: '3', title: 'Финальный этап: Ахметова А. К.', time: '10:00', date: 'Завтра', type: 'online', location: 'Google Meet', badge: 'Бухгалтер' },
  { id: '4', title: 'One-to-One с руководителем', time: '16:30', date: 'Завтра', type: 'offline', location: 'Кабинет 302', badge: 'Регулярная' },
];

export default function HrOverviewPage() {
  const persona = useDeveloperStore((state) => state.persona);
  const locale = useDeveloperStore((state) => state.locale);
  const canOpen = usePermission('hr.read');
  const isHr = UNIFIED_HR_WORKSPACE || persona === 'hr-specialist';
  const permissions = getPermissions(persona);
  const attentionScope: HiringRequestScope = permissions.includes('hiring.approve')
    ? 'inbox'
    : permissions.includes('hiring.receive') ? 'received' : 'mine';
  const overview = useQuery({ queryKey: ['hr', 'overview'], queryFn: () => hrRepository.getOverview(), enabled: canOpen && isHr });
  const employee = useQuery({ queryKey: ['hr', 'employee', 'me'], queryFn: () => hrRepository.getCurrentEmployee(), enabled: canOpen && !isHr });
  const leaveRequests = useQuery({ queryKey: ['hr', 'leave'], queryFn: () => hrRepository.listLeaveRequests(), enabled: canOpen });
  const hiringActivity = useQuery({ queryKey: ['hiring-requests', attentionScope, persona], queryFn: () => hiringRequestsApi.list(attentionScope), enabled: canOpen && isHr });

  if (!canOpen) return <div className="hr-access-denied"><span>HR</span><h1>Рабочее пространство недоступно</h1><p>Выбранная роль не участвует в HR self-service или кадровых процессах.</p><Link className="secondary-button" to="/">На главную</Link></div>;
  if (overview.isLoading || employee.isLoading || leaveRequests.isLoading || hiringActivity.isLoading) return <QueryState />;
  const error = overview.error || employee.error || leaveRequests.error || hiringActivity.error;
  if (error) return <QueryState error={error} retry={() => { overview.refetch(); employee.refetch(); leaveRequests.refetch(); hiringActivity.refetch(); }} />;

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
  const messages = hiringActivity.data!.filter((item) => !['draft', 'pdf_generated'].includes(item.status));
  const pending = permissions.includes('hiring.approve') ? messages : [];
  const workforceTotal = Math.max(1, stats.activeEmployees + stats.onLeave + stats.onBusinessTrip + stats.onSickLeave);
  const presenceRate = Math.round(stats.activeEmployees / workforceTotal * 100);
  const workforceChart = [
    { label: 'Активны', value: stats.activeEmployees, color: 'var(--teal)', detail: 'На рабочем месте', to: '/hr/employees' },
    { label: 'В отпуске', value: stats.onLeave, color: 'var(--gold)', detail: 'Плановое отсутствие', to: '/hr/leave' },
    { label: 'Командировка', value: stats.onBusinessTrip, color: 'var(--violet)', detail: 'Служебная поездка', to: '/hr/calendar' },
    { label: 'Больничный', value: stats.onSickLeave, color: 'var(--coral)', detail: 'Нетрудоспособность', to: '/hr/sick-leave' },
  ];
  return <>
    <PageHeader eyebrow="HR · Главная" title="Рабочее пространство" />
    
    <div className="dashboard-staggered-layout">
      {/* Row 1: 55 / 45 */}
      <div className="staggered-row row-55-45">
        {/* Left Column (55%): Approvals */}
        <div className="col-55">
          <section className="workspace-card approvals-section" aria-label="Панель согласований найма">
            <header className="card-section-header">
              <div className="card-title-wrap">
                <ShieldCheck size={20} className="icon-amber" />
                <h2>Согласования</h2>
                <span className={`hub-badge badge-amber ${pending.length ? 'active' : ''}`}>{pending.length}</span>
              </div>
              <Link className="card-header-link" to="/hr/approvals">Все согласования <ArrowRight size={14} /></Link>
            </header>

            <div className="card-section-content">
              {pending.length ? (
                <div className="hub-decisions-list">
                  {pending.slice(0, 3).map((request) => (
                    <Link to={`/hiring/requests/${request.id}`} className="hub-decision-row-card" key={request.id}>
                      <div className="hub-row-header">
                        <div className="hub-row-candidate">
                          <strong>{request.candidateName || 'Новый сотрудник'}</strong>
                          <span className="hub-row-meta">
                            {String(request.employmentData.department ?? 'Подразделение не указано')} · {String(request.employmentData.position ?? 'Должность не указана')}
                          </span>
                        </div>
                        <span className="hub-row-tag tag-urgent">Требует действия</span>
                      </div>

                      <div className="hub-row-body hub-request-facts">
                        <span><small>Дата выхода</small><strong>{String(request.employmentData.startDate ?? '—')}</strong></span>
                        <span><small>Формат</small><strong>{String(request.employmentData.workArrangement ?? '—')}</strong></span>
                        <span><small>Документы</small><strong>{request.attachments?.length ?? 0}</strong></span>
                      </div>

                      <div className="hub-row-footer">
                        <span className="hub-row-info">
                          Номер: <code>{request.requestNumber}</code> · Пакет зарегистрирован
                        </span>
                        <span className="hub-row-action-btn">
                          Рассмотреть <ArrowRight size={14} />
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <div className="hub-empty-state state-success">
                  <div className="hub-empty-icon">
                    <CheckCircle2 size={32} />
                    <div className="pulse-glow" />
                  </div>
                  <strong>Отличная работа!</strong>
                  <p>Все входящие заявки согласованы. На вашей роли нет документов, требующих срочного решения.</p>
                </div>
              )}
            </div>
          </section>
        </div>

        {/* Right Column (45%): Staff Status / Presence */}
        <div className="col-45">
          <section className="workspace-card presence-section" aria-label="Статус персонала">
            <header className="card-section-header">
              <div className="card-title-wrap">
                <UsersRound size={18} className="icon-teal" />
                <h2>Статус персонала</h2>
                <span className="hub-badge badge-blue">{workforceTotal}</span>
              </div>
              <span className="card-header-meta">присутствие</span>
            </header>
            <div className="card-section-content">
              <DonutChart data={workforceChart} centerValue={`${presenceRate}%`} centerLabel="активны" ariaLabel="Распределение сотрудников по типу присутствия" />
            </div>
          </section>
        </div>
      </div>

      {/* Row 2: 45 / 55 */}
      <div className="staggered-row row-45-55">
        {/* Left Column (45%): Meeting Plan */}
        <div className="col-45">
          <section className="workspace-card meetings-section" aria-label="План встреч">
            <header className="card-section-header">
              <div className="card-title-wrap">
                <Calendar size={18} className="icon-teal" />
                <h2>План встреч</h2>
                <span className="hub-badge badge-blue">{mockMeetings.length}</span>
              </div>
              <span className="card-header-meta">ближайшие</span>
            </header>
            <div className="card-section-content">
              <div className="meetings-list">
                {mockMeetings.map((meeting) => (
                  <div className="meeting-row-card" key={meeting.id}>
                    <div className="meeting-time-box">
                      <span className="meeting-date">{meeting.date}</span>
                      <span className="meeting-time">{meeting.time}</span>
                    </div>
                    <div className="meeting-info">
                      <div className="meeting-title-wrap">
                        <strong>{meeting.title}</strong>
                        <span className={`meeting-badge ${meeting.type}`}>{meeting.badge}</span>
                      </div>
                      <div className="meeting-location">
                        {meeting.type === 'online' ? <Video size={12} className="loc-icon" /> : <MapPin size={12} className="loc-icon" />}
                        <span>{meeting.location}</span>
                      </div>
                    </div>
                    {meeting.type === 'online' && (
                      <a href="https://meet.google.com" target="_blank" rel="noopener noreferrer" className="meeting-action-link">
                        Войти
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </section>
        </div>

        {/* Right Column (55%): Incoming Messages */}
        <div className="col-55">
          <section className="workspace-card updates-section" aria-label="Входящие сообщения">
            <header className="card-section-header">
              <div className="card-title-wrap">
                <Inbox size={18} className="icon-blue" />
                <h2>Входящие сообщения</h2>
                <span className="hub-badge badge-blue">{messages.length}</span>
              </div>
              <Link className="card-header-link" to="/hr/approvals">Все сообщения <ArrowRight size={14} /></Link>
            </header>

            <div className="card-section-content">
              {messages.length ? (
                <div className="hub-updates-timeline">
                  {messages.slice(0, 4).map((item) => {
                    const isPending = pending.some((request) => request.id === item.id);
                    return (
                      <Link to={`/hiring/requests/${item.id}`} className={`hub-timeline-item ${isPending ? 'highlighted' : ''}`} key={item.id}>
                        <div className="hub-timeline-badge">
                          <span className={`status-pulse pulse-${item.status}`} />
                        </div>
                        <div className="hub-timeline-body">
                          <div className="hub-timeline-title">
                            <strong>{item.candidateName || 'Новый сотрудник'}</strong>
                            <span className="hub-timeline-time">{formatDate(item.createdAt, locale, 'dd MMM')}</span>
                          </div>
                          <p className="hub-timeline-text">
                            Заявка <code>{item.requestNumber}</code> переведена в статус <strong>{hiringStatusLabels[item.status] ?? item.status}</strong>
                          </p>
                          <div className="hub-timeline-footer">
                            <span>Пакет документов</span>
                            <span className="hub-timeline-action">Открыть <ArrowRight size={12} /></span>
                          </div>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              ) : (
                <div className="hub-empty-state">
                  <div className="hub-empty-icon mini">
                    <Inbox size={24} />
                  </div>
                  <strong>Лента пуста</strong>
                  <p>Пока нет входящих сообщений.</p>
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  </>;
}
