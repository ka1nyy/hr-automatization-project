import { useQuery } from '@tanstack/react-query';
import { CalendarDays, CheckCircle2, ChevronRight, ClipboardCheck, FileText, HeartPulse, Plus, UserMinus } from 'lucide-react';
import { Link } from 'react-router-dom';
import { PageHeader, QueryState, Section } from '../../../shared/components';
import { usePermission } from '../../../shared/permissions';
import { plannedHrService, type PlannedEvent, type PlannedEventKind } from '../mocks/plannedHrService';

type PlannedPageKind = 'calendar' | 'sick' | 'terminations' | 'documents' | 'approvals';

const pageConfig: Record<PlannedPageKind, { eyebrow: string; title: string; description: string; action: string; eventKinds: PlannedEventKind[] }> = {
  calendar: { eyebrow: 'HR · Календарь', title: 'Календарь', description: 'Отпуска, больничные, выходы и кадровые события в одном месте.', action: 'Добавить событие', eventKinds: ['leave', 'sick', 'hiring', 'dismissal', 'approval'] },
  sick: { eyebrow: 'HR · Отсутствия', title: 'Больничные', description: 'Учёт листов нетрудоспособности и контроль подтверждающих документов.', action: 'Зарегистрировать', eventKinds: ['sick'] },
  terminations: { eyebrow: 'HR · Кадровые движения', title: 'Увольнения', description: 'Заявления, обходные листы и контроль завершения трудовых отношений.', action: 'Начать увольнение', eventKinds: ['dismissal'] },
  documents: { eyebrow: 'HR · Архив', title: 'Документы', description: 'Личные дела, приказы и кадровые документы с контролем комплектности.', action: 'Загрузить документ', eventKinds: ['document'] },
  approvals: { eyebrow: 'HR · Workflow', title: 'Согласования', description: 'Единая очередь HR-решений с маршрутом, сроками и текущим этапом.', action: 'Настроить маршрт', eventKinds: ['approval'] },
};

const kindLabels: Record<PlannedEventKind, string> = { leave: 'Отпуск', sick: 'Больничный', hiring: 'Найм', dismissal: 'Увольнение', approval: 'Согласование', document: 'Документ' };
const statusLabels = { planned: 'Запланировано', review: 'На рассмотрении', approved: 'Согласовано', attention: 'Требует внимания' };

function eventIcon(event: PlannedEvent) {
  if (event.kind === 'sick') return <HeartPulse size={18} />;
  if (event.kind === 'dismissal') return <UserMinus size={18} />;
  if (event.kind === 'document') return <FileText size={18} />;
  if (event.kind === 'approval') return <ClipboardCheck size={18} />;
  return <CalendarDays size={18} />;
}

export default function HrPlannedPage({ kind }: { kind: PlannedPageKind }) {
  const config = pageConfig[kind];
  const canOpen = usePermission('hr.employees.read');
  const query = useQuery({ queryKey: ['hr', 'planned-events'], queryFn: () => plannedHrService.listEvents(), enabled: canOpen });
  if (!canOpen) return <div className="hr-access-denied"><span>HR</span><h1>Доступ ограничен</h1><p>Этот раздел доступен только HR-ролям.</p><Link className="secondary-button" to="/">На главную</Link></div>;
  if (query.isLoading) return <QueryState />;
  if (query.error) return <QueryState error={query.error} retry={() => query.refetch()} />;
  const items = (query.data ?? []).filter((event) => config.eventKinds.includes(event.kind));
  const activeCount = items.filter((item) => item.status === 'review' || item.status === 'attention').length;

  return <>
    <PageHeader eyebrow={config.eyebrow} title={config.title} description={config.description} actions={<button type="button" className="primary-button"><Plus size={17} />{config.action}</button>} />
    <div className="planned-metric-grid">
      <article><span><CalendarDays size={20} /></span><div><small>Всего записей</small><strong>{items.length}</strong><em>в текущем периоде</em></div></article>
      <article><span><ClipboardCheck size={20} /></span><div><small>Требуют действия</small><strong>{activeCount}</strong><em>в очереди HR</em></div></article>
      <article><span><CheckCircle2 size={20} /></span><div><small>Завершено</small><strong>{items.filter((item) => item.status === 'approved').length}</strong><em>без замечаний</em></div></article>
    </div>
    <Section title={kind === 'calendar' ? 'Ближайшие события' : 'Текущие записи'} meta="Frontend-ready · API pending">
      <div className="planned-list">
        {items.map((event) => <article key={event.id}>
          <span className={`planned-event-icon kind-${event.kind}`}>{eventIcon(event)}</span>
          <div><div><span className="planned-kind">{kindLabels[event.kind]}</span><span className={`planned-status status-${event.status}`}>{statusLabels[event.status]}</span></div><strong>{event.title}</strong><small>{event.person} · {event.detail}</small></div>
          <time dateTime={event.date}>{new Date(event.date).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' })}{event.endDate && <small>— {new Date(event.endDate).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' })}</small>}</time>
          <button type="button" className="icon-button" aria-label={`Открыть ${event.title}`}><ChevronRight size={18} /></button>
        </article>)}
      </div>
    </Section>
  </>;
}
