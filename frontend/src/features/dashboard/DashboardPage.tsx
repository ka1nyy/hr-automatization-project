import { useQuery } from '@tanstack/react-query';
import { AlertOctagon, ArrowRight, CheckCircle2, Clock3, FileCheck2, FileInput, PenTool, Send, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { repositories } from '../../repositories';
import { LinkArrow, PageHeader, QueryState, Section } from '../../shared/components';
import { formatDate, statusLabels } from '../../shared/format';
import { useDeveloperStore } from '../../shared/store';
import HrOverviewPage from '../hr/pages/HrOverviewPage';

export default function DashboardPage() {
  const persona = useDeveloperStore((state) => state.persona);
  return persona === 'hr-specialist' ? <HrOverviewPage /> : <OperationsDashboard />;
}

function OperationsDashboard() {
  const locale = useDeveloperStore((state) => state.locale);
  const snapshot = useQuery({ queryKey: ['dashboard'], queryFn: () => repositories.operations.dashboard() });
  const correspondence = useQuery({ queryKey: ['incoming'], queryFn: () => repositories.correspondence.listIncoming() });
  const tasks = useQuery({ queryKey: ['tasks'], queryFn: () => repositories.tasks.list() });
  if (snapshot.isLoading || correspondence.isLoading || tasks.isLoading) return <QueryState />;
  if (snapshot.error || correspondence.error || tasks.error) return <QueryState error={(snapshot.error || correspondence.error || tasks.error) as Error} retry={() => { snapshot.refetch(); correspondence.refetch(); tasks.refetch(); }} />;
  const stats = snapshot.data!;
  return <>
    <PageHeader eyebrow="Операционный день · 14 июля 2026" title="Центр управления" actions={<><button className="secondary-button"><Sparkles size={16} /> Сводка дня</button><Link className="primary-button" to="/correspondence/incoming/new"><FileInput size={16} /> Регистрация письма</Link></>} />
    <div className="metric-grid">
      <article><span className="metric-icon tone-teal"><FileInput size={18} /></span><div><small>Поступило сегодня</small><strong>{stats.incomingToday}</strong><em>+2 за последний час</em></div></article>
      <article><span className="metric-icon tone-gold"><PenTool size={18} /></span><div><small>Ожидают резолюции</small><strong>{stats.awaitingResolution}</strong><em>3 срочных</em></div></article>
      <article><span className="metric-icon tone-violet"><Clock3 size={18} /></span><div><small>Активные задачи</small><strong>{stats.activeTasks}</strong><em>В работе сотрудников</em></div></article>
      <article><span className="metric-icon tone-coral"><AlertOctagon size={18} /></span><div><small>Просрочено</small><strong>{stats.overdue}</strong><em>Требуют внимания</em></div></article>
      <article><span className="metric-icon tone-gold"><FileCheck2 size={18} /></span><div><small>На подписи</small><strong>{stats.signatureQueue}</strong><em>ЭЦП mock</em></div></article>
      <article><span className="metric-icon tone-emerald"><Send size={18} /></span><div><small>К отправке</small><strong>{stats.dispatchQueue}</strong><em>Секретариат</em></div></article>
    </div>
    <div className="dashboard-grid">
      <Section title="Операционная очередь" meta="Обновлено сейчас" className="span-two">
        <div className="queue-table"><div className="table-head"><span>Документ</span><span>Отправитель</span><span>Этап</span><span>Срок</span><span /></div>{correspondence.data!.slice(0, 10).map((item) => <Link to={`/correspondence/incoming/${item.id}`} className="table-row" key={item.id}><span><strong>{item.number}</strong><small>{item.subject}</small></span><span>{item.sender}</span><span><i className={`status-dot status-${item.status}`} />{statusLabels[item.status]}</span><span className={item.priority === 'urgent' ? 'text-coral' : ''}>{formatDate(item.dueDate, locale, 'dd MMM')}</span><LinkArrow /></Link>)}</div>
        <Link className="panel-link" to="/correspondence/incoming">Весь реестр <ArrowRight size={15} /></Link>
      </Section>
      <Section title="Мои ближайшие задачи" meta={`${tasks.data!.length} активных`}>
        <div className="task-compact-list">{tasks.data!.slice(0, 4).map((task) => <Link to="/tasks" key={task.id}><span className={`priority-line priority-${task.priority}`} /><span><strong>{task.title}</strong><small>{task.documentNumber} · до {formatDate(task.dueDate, locale, 'dd MMM')}</small></span><ArrowRight size={15} /></Link>)}</div>
      </Section>
      <Section title="Маршрут дня" meta="Входящая корреспонденция v7" className="span-two">
        <div className="route-strip">{['Регистрация', 'Резолюция', 'Исполнение', 'Согласование', 'ЭЦП', 'Отправка'].map((step, index) => <div className={index < 2 ? 'done' : index === 2 ? 'active' : ''} key={step}><span>{index < 2 ? <CheckCircle2 size={16} /> : index + 1}</span><strong>{step}</strong>{index < 5 && <i />}</div>)}</div>
      </Section>
      <Section title="Контроль SLA" meta="Последние 7 дней">
        <div className="sla-visual"><div className="sla-ring"><strong>91%</strong><span>в срок</span></div><div className="sla-legend"><span><i className="tone-emerald" /> 118 завершено</span><span><i className="tone-gold" /> 9 под риском</span><span><i className="tone-coral" /> 3 просрочено</span></div></div>
      </Section>
    </div>
  </>;
}
