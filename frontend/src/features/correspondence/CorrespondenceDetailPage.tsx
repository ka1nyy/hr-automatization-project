import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, ArrowLeft, CheckCircle2, FileText, Forward, UserRound } from 'lucide-react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { repositories } from '../../repositories';
import { PageHeader, QueryState, Section } from '../../shared/components';
import { formatDate, statusLabels } from '../../shared/format';
import { PermissionGate } from '../../shared/permissions';
import { useDeveloperStore } from '../../shared/store';

export default function CorrespondenceDetailPage() {
  const { id = '' } = useParams();
  const [searchParams] = useSearchParams();
  const locale = useDeveloperStore((state) => state.locale);
  const queryClient = useQueryClient();
  const result = useQuery({ queryKey: ['incoming', id], queryFn: () => repositories.correspondence.getIncoming(id) });
  const resolution = useMutation({ mutationFn: () => repositories.correspondence.sendForResolution(id), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['incoming'] }); } });
  if (result.isLoading) return <QueryState />;
  if (result.error || !result.data) return <QueryState error={result.error ?? new Error('Документ не найден')} retry={() => result.refetch()} />;
  const item = result.data;
  const steps = ['registered', 'resolution', 'execution', 'approval', 'signature', 'dispatch', 'completed'];
  const activeIndex = steps.indexOf(item.status);
  return <>
    {searchParams.get('registered') && <div className="success-banner"><CheckCircle2 size={20} /><span><strong>Письмо зарегистрировано</strong>Registry Service присвоил официальный номер {item.number}.</span></div>}
    <PageHeader eyebrow={`Входящая корреспонденция · ${item.number}`} title={item.subject} description={`${item.sender} · ${item.senderNumber} от ${formatDate(item.senderDate, locale)}`} actions={<><Link className="secondary-button" to="/correspondence/incoming"><ArrowLeft size={16} /> Реестр</Link><PermissionGate permission="correspondence.register"><button className="primary-button" onClick={() => resolution.mutate()} disabled={item.status !== 'registered' || resolution.isPending}><Forward size={16} /> На резолюцию</button></PermissionGate></>} />
    <div className="case-status-bar"><span className={`status-pill status-${item.status}`}><i />{statusLabels[item.status]}</span><span><strong>Приоритет</strong>{item.priority === 'urgent' ? 'Срочный' : item.priority === 'high' ? 'Высокий' : 'Обычный'}</span><span><strong>Срок ответа</strong>{formatDate(item.dueDate, locale)}</span><span><strong>Ответственный</strong>{item.executor}</span><span className="sla-count"><strong>SLA</strong>1д 04ч</span></div>
    <div className="case-layout">
      <div className="case-main">
        <Section title="Оригинал входящего документа" meta="Предпросмотр"><div className="document-preview"><div className="paper"><header><span className="seal">ҚР</span><div><strong>{item.sender}</strong><small>Официальная корреспонденция</small></div></header><div className="paper-meta"><span>№ {item.senderNumber}</span><span>{formatDate(item.senderDate, locale)}</span></div><h3>{item.subject}</h3><p>{item.summary}</p><p>Просим рассмотреть обращение и представить официальный ответ в установленный срок. Приложенные материалы являются неотъемлемой частью настоящего письма.</p><footer><span>Руководитель организации</span><strong>ЭЦП подтверждена</strong></footer></div></div></Section>
        <Section title="Регистрационные данные"><dl className="metadata-grid"><div><dt>Внутренний номер</dt><dd>{item.number}</dd></div><div><dt>Получено</dt><dd>{formatDate(item.receivedAt, locale, 'dd MMM yyyy · HH:mm')}</dd></div><div><dt>Канал</dt><dd>{item.channel}</dd></div><div><dt>Тип документа</dt><dd>{item.documentType}</dd></div><div><dt>Подразделение</dt><dd>{item.department}</dd></div><div><dt>Получатель резолюции</dt><dd>{item.executive}</dd></div><div><dt>Конфиденциальность</dt><dd>{item.confidentiality === 'restricted' ? 'Ограниченный доступ' : 'Внутренний документ'}</dd></div><div><dt>Теги</dt><dd>{item.tags.join(' · ') || 'Нет тегов'}</dd></div></dl></Section>
        {item.attachments.length > 0 && <Section title="Вложения" meta={`${item.attachments.length} файла`}><div className="attachment-list">{item.attachments.map((file) => <div key={file.id}><span><FileText size={19} /></span><div><strong>{file.name}</strong><small>{file.size} · {file.kind === 'scan' ? 'Оригинал' : 'Приложение'}</small></div></div>)}</div></Section>}
      </div>
      <aside className="case-aside">
        <Section title="Ход процесса" meta="v7"><div className="process-timeline">{['Регистрация', 'Резолюция', 'Исполнение', 'Согласование', 'Подписание', 'Отправка'].map((step, index) => <div className={index < activeIndex ? 'done' : index === activeIndex ? 'active' : ''} key={step}><span>{index < activeIndex ? <CheckCircle2 size={15} /> : index + 1}</span><div><strong>{step}</strong><small>{index === activeIndex ? item.workflowStep : index < activeIndex ? 'Завершено' : 'Ожидает'}</small></div></div>)}</div></Section>
        <Section title="Участники"><div className="participant-list"><div><span className="avatar small">АН</span><span><strong>{item.executive}</strong><small>Руководитель</small></span></div><div><span className="avatar small">МС</span><span><strong>{item.executor}</strong><small>Основной исполнитель</small></span></div><div><span className="avatar small ghost"><UserRound size={15} /></span><span><strong>legal-contract-reviewers</strong><small>Группа кандидатов</small></span></div></div></Section>
        <Section title="История действий"><div className="audit-list">{item.audit.map((event) => <div key={event.id}><i /><span><strong>{event.action}</strong><small>{event.actor} · {formatDate(event.at, locale, 'dd MMM · HH:mm')}</small><p>{event.detail}</p></span></div>)}</div></Section>
        {item.confidentiality === 'restricted' && <div className="restricted-note"><AlertCircle size={18} /><span><strong>Ограниченный документ</strong>Часть полей скрыта политикой ABAC.</span></div>}
      </aside>
    </div>
  </>;
}
