import { useQuery } from '@tanstack/react-query';
import { ArrowRight, FileCheck2, Inbox, Plus, RefreshCw } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { PageHeader } from '../../../shared/components';
import { getPermissions } from '../../../shared/permissions';
import { useDeveloperStore } from '../../../shared/store';
import { hiringRequestsApi } from '../api/hiringRequests';

const labels: Record<string, string> = { draft: 'Черновик', pdf_generated: 'PDF готов', under_review: 'На согласовании', returned: 'Возвращено', rejected: 'Отклонено', final_approved: 'Финально согласовано', dispatched: 'Отправлено', partially_acknowledged: 'Получено частично', completed: 'Завершено' };

export default function HiringRequestsPage() {
  const pathname = useLocation().pathname;
  const persona = useDeveloperStore((state) => state.persona);
  const permissions = getPermissions(persona);
  const scope = pathname.endsWith('/inbox') ? 'inbox' : pathname.endsWith('/received') ? 'received' : permissions.includes('hiring.monitor') ? undefined : 'mine';
  const query = useQuery({ queryKey: ['hiring-requests', scope, persona], queryFn: () => hiringRequestsApi.list(scope) });
  const title = scope === 'inbox' ? 'Входящие согласования' : scope === 'received' ? 'Документы новых сотрудников' : 'Заявки на найм';
  return <>
    <PageHeader eyebrow="HR · Сквозной процесс" title={title} description={scope === 'inbox' ? 'Здесь только заявки, на которых сейчас требуется ваше решение.' : scope === 'received' ? 'Пакеты, направленные вашему подразделению после финального согласования.' : 'Черновики, согласование, финальные документы и отправка получателям — в одном месте.'} actions={permissions.includes('hiring.initiate') ? <Link className="primary-button" to="/hr/employees?add=true"><Plus size={16} />Создать заявку</Link> : undefined} />
    <div className="hiring-list-toolbar"><span><Inbox size={17} />{query.data?.length ?? 0} заявок</span><button className="secondary-button" onClick={() => void query.refetch()}><RefreshCw size={15} />Обновить</button></div>
    {query.isError ? <div className="api-error-card"><strong>Не удалось загрузить заявки</strong><p>{query.error instanceof Error ? query.error.message : 'Ошибка API'}</p></div> : query.isLoading ? <div className="hiring-empty">Загрузка заявок…</div> : query.data?.length ? <div className="hiring-request-list">{query.data.map((request) => <Link to={`/hiring/requests/${request.id}`} key={request.id} className="hiring-request-card"><span className="hiring-request-icon"><FileCheck2 size={20} /></span><div><small>{request.requestNumber}</small><strong>{request.candidateName || 'Кандидат не указан'}</strong><p>{String(request.employmentData.department ?? 'Подразделение не выбрано')} · {String(request.employmentData.position ?? 'Должность не выбрана')}</p></div><span className={`hiring-status ${request.status}`}>{labels[request.status] ?? request.status}</span><div className="hiring-request-stage"><small>{request.currentStageName ?? 'Этап завершён'}</small><time>{new Date(request.createdAt).toLocaleDateString('ru-RU')}</time></div><ArrowRight size={18} /></Link>)}</div> : <div className="hiring-empty"><span><FileCheck2 size={28} /></span><strong>Очередь пуста</strong><p>Когда появится заявка, требующая вашего действия, она будет показана здесь.</p></div>}
  </>;
}
