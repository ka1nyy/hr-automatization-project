import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BriefcaseBusiness, Check, Download, FileText, GraduationCap, Send, UserRound, UserPlus, Undo2, X } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { PageHeader } from '../../../shared/components';
import { getPermissions } from '../../../shared/permissions';
import { useDeveloperStore } from '../../../shared/store';
import { canPersonaAcknowledgeRequest, canPersonaApproveRequest, hiringRequestsApi } from '../api/hiringRequests';

export default function HiringRequestDetailsPage() {
  const { id = '' } = useParams(); const persona = useDeveloperStore((state) => state.persona); const permissions = getPermissions(persona);
  const client = useQueryClient(); const [comment, setComment] = useState(''); const [error, setError] = useState('');
  const query = useQuery({ queryKey: ['hiring-request', id, persona], queryFn: () => hiringRequestsApi.get(id), enabled: Boolean(id) });
  const action = useMutation({ mutationFn: async (kind: 'approve' | 'return' | 'reject' | 'dispatch' | 'acknowledge') => {
    if (!query.data) throw new Error('Заявка не загружена');
    if ((kind === 'return' || kind === 'reject') && !comment.trim()) throw new Error('Для возврата или отклонения укажите комментарий');
    if (kind === 'dispatch') return hiringRequestsApi.dispatch(id, query.data.revision);
    if (kind === 'acknowledge') return hiringRequestsApi.acknowledge(id, query.data.revision, comment);
    return hiringRequestsApi.decide(id, query.data.revision, kind, comment);
  }, onSuccess: async () => {
    setComment(''); setError('');
    await Promise.all([
      client.invalidateQueries({ queryKey: ['hiring-request', id] }),
      client.invalidateQueries({ queryKey: ['hiring-requests'] })
    ]);
  }, onError: (value) => setError(value instanceof Error ? value.message : 'Действие не выполнено') });
  const request = query.data;
  if (query.isLoading) return <div className="hiring-empty">Загрузка заявки…</div>;
  if (!request) return <div className="api-error-card"><strong>Заявка недоступна</strong><p>{query.error instanceof Error ? query.error.message : 'Проверьте права доступа.'}</p></div>;
  const finalVersion = request.finalPdfVersionId ?? request.pdfVersionId;
  const canApprove = permissions.includes('hiring.approve') && canPersonaApproveRequest(persona, request);
  const canAcknowledge = permissions.includes('hiring.receive') && canPersonaAcknowledgeRequest(persona, request);
  return <>
    <PageHeader eyebrow={request.requestNumber} title={request.candidateName} description={`${String(request.employmentData.position ?? 'Должность не указана')} · ${String(request.employmentData.department ?? 'Подразделение не указано')}`} actions={<Link className="secondary-button" to={permissions.includes('hiring.approve') ? '/hiring/inbox' : permissions.includes('hiring.receive') ? '/hiring/received' : '/hiring/requests'}>Назад к очереди</Link>} />
    {error && <div className="api-error-card"><strong>Действие не выполнено</strong><p>{error}</p></div>}
    <div className="hiring-detail-grid"><section className="hiring-detail-main hiring-request-information"><header><span><UserRound size={20} /></span><div><small>ЗАЯВЛЕНИЕ НА НАЙМ</small><strong>Информация о кандидате</strong><p>Сведения из зарегистрированного пакета документов</p></div></header><div className="hiring-summary-grid"><dl><dt>Инициатор</dt><dd>{request.initiatorName}</dd></dl><dl><dt>ИИН</dt><dd>{String(request.personal.iin ?? 'Недоступен')}</dd></dl><dl><dt>Дата выхода</dt><dd>{String(request.employmentData.startDate ?? '—')}</dd></dl><dl><dt>Формат</dt><dd>{String(request.employmentData.workArrangement ?? '—')}</dd></dl></div><div className="hiring-information-section"><h3><BriefcaseBusiness size={17} />Параметры трудоустройства</h3><div className="hiring-information-grid"><dl><dt>Подразделение</dt><dd>{String(request.employmentData.department ?? 'Не указано')}</dd></dl><dl><dt>Должность</dt><dd>{String(request.employmentData.position ?? 'Не указана')}</dd></dl><dl><dt>Место работы</dt><dd>{String(request.employmentData.workplace ?? 'Не указано')}</dd></dl><dl><dt>График</dt><dd>{String(request.employmentData.schedule ?? 'Не указан')}</dd></dl><dl><dt>Тип занятости</dt><dd>{String(request.employmentData.employmentType ?? 'Не указан')}</dd></dl><dl><dt>Ставка</dt><dd>{request.employmentData.fte ? `${String(request.employmentData.fte)} FTE` : 'Не указана'}</dd></dl></div></div><div className="hiring-information-section"><h3><GraduationCap size={17} />Образование и опыт</h3><div className="hiring-information-grid"><dl><dt>Уровень образования</dt><dd>{String(request.educationData.educationLevel ?? 'Не указан')}</dd></dl><dl><dt>Учебное заведение</dt><dd>{String(request.educationData.institution ?? 'Не указано')}</dd></dl><dl><dt>Специализация</dt><dd>{String(request.educationData.specialization ?? 'Не указана')}</dd></dl><dl><dt>Общий опыт</dt><dd>{String(request.educationData.totalExperience ?? 'Не указан')}</dd></dl></div></div><div className="hiring-private-route-note"><FileText size={18} /><div><strong>Заявление зарегистрировано</strong><p>Пакет передан ответственным подразделениям. Внутренний маршрут рассмотрения не отображается.</p></div></div></section>
      <aside className="hiring-document-panel"><h3><FileText size={18} />Пакет документов</h3>{finalVersion && <a className="primary-button full" href={hiringRequestsApi.downloadUrl(id, finalVersion, true)} target="_blank" rel="noreferrer"><FileText size={16} />Открыть PDF</a>}<div className="hiring-files">{request.attachments.map((file) => <a href={hiringRequestsApi.downloadUrl(id, file.versionId)} key={file.id}><span><strong>{file.originalFilename}</strong><small>{file.category === 'identity' ? 'Удостоверение личности' : 'Диплом'} · {(file.sizeBytes / 1024 / 1024).toFixed(2)} МБ</small></span><Download size={16} /></a>)}</div>
      {(canApprove || canAcknowledge) && <div className="hiring-action-box"><label>Комментарий<textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Добавьте пояснение к решению" /></label>{canApprove ? <div><button disabled={action.isPending} className="success-button" onClick={() => action.mutate('approve')}><Check size={16} />Согласовать</button><button disabled={action.isPending} className="secondary-button" onClick={() => action.mutate('return')}><Undo2 size={16} />Вернуть</button><button disabled={action.isPending} className="danger-button" onClick={() => action.mutate('reject')}><X size={16} />Отклонить</button></div> : <button disabled={action.isPending} className="primary-button full" onClick={() => action.mutate('acknowledge')}><Check size={16} />Подтвердить получение</button>}</div>}
      {permissions.includes('hiring.initiate') && request.status === 'final_approved' && <button disabled={action.isPending} className="primary-button full" onClick={() => action.mutate('dispatch')}><Send size={16} />Отправить в бухгалтерию и IT</button>}
      {request.status === 'completed' && request.hiredEmployee && <div className="hiring-action-box lifecycle-hire-box lifecycle-hire-complete"><div className="lifecycle-action-title"><span><UserPlus size={18} /></span><div><strong>Сотрудник создан автоматически</strong><small>Карточка сформирована после подтверждения бухгалтерии и IT</small></div></div><dl><dt>Табельный номер</dt><dd>{request.hiredEmployee.employeeNumber}</dd><dt>Корпоративный e-mail</dt><dd>{request.hiredEmployee.corporateEmail ?? '—'}</dd></dl><Link className="primary-button full" to={`/hr/employees/${request.hiredEmployee.id}?hired=1`}>Открыть профиль сотрудника</Link></div>}</aside></div>
  </>;
}
