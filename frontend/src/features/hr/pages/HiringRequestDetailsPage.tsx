import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BriefcaseBusiness, Check, Download, FileText, GraduationCap, Send, UserRound, UserPlus, Undo2, X } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { PageHeader } from '../../../shared/components';
import { getPermissions } from '../../../shared/permissions';
import { useDeveloperStore } from '../../../shared/store';
import { formatDate } from '../../../shared/format';
import { canPersonaAcknowledgeRequest, canPersonaApproveRequest, hiringRequestsApi } from '../api/hiringRequests';

export default function HiringRequestDetailsPage() {
  const { id = '' } = useParams();
  const persona = useDeveloperStore((state) => state.persona);
  const locale = useDeveloperStore((state) => state.locale);
  const permissions = getPermissions(persona);
  const client = useQueryClient();
  
  const [comment, setComment] = useState('');
  const [error, setError] = useState('');
  
  const query = useQuery({ 
    queryKey: ['hiring-request', id, persona], 
    queryFn: () => hiringRequestsApi.get(id), 
    enabled: Boolean(id) 
  });
  
  const action = useMutation({ 
    mutationFn: async (kind: 'approve' | 'return' | 'reject' | 'dispatch' | 'acknowledge') => {
      if (!query.data) throw new Error('Заявка не загружена');
      if ((kind === 'return' || kind === 'reject') && !comment.trim()) {
        throw new Error('Для возврата или отклонения укажите комментарий');
      }
      if (kind === 'dispatch') return hiringRequestsApi.dispatch(id, query.data.revision);
      if (kind === 'acknowledge') return hiringRequestsApi.acknowledge(id, query.data.revision, comment);
      return hiringRequestsApi.decide(id, query.data.revision, kind, comment);
    }, 
    onSuccess: async () => {
      setComment(''); 
      setError('');
      await Promise.all([
        client.invalidateQueries({ queryKey: ['hiring-request', id] }),
        client.invalidateQueries({ queryKey: ['hiring-requests'] })
      ]);
    }, 
    onError: (value) => setError(value instanceof Error ? value.message : 'Действие не выполнено') 
  });

  const request = query.data;
  if (query.isLoading) return <div className="hiring-empty">Загрузка заявки…</div>;
  if (!request) return <div className="api-error-card"><strong>Заявка недоступна</strong><p>{query.error instanceof Error ? query.error.message : 'Проверьте права доступа.'}</p></div>;
  
  const finalVersion = request.finalPdfVersionId ?? request.pdfVersionId;
  const canApprove = permissions.includes('hiring.approve') && canPersonaApproveRequest(persona, request);
  const canAcknowledge = permissions.includes('hiring.receive') && canPersonaAcknowledgeRequest(persona, request);

  return <>
    <PageHeader 
      eyebrow={request.requestNumber} 
      title={request.candidateName} 
      description={`${String(request.employmentData.position ?? 'Должность не указана')} · ${String(request.employmentData.department ?? 'Подразделение не указано')}`} 
      actions={<Link className="secondary-button" to={permissions.includes('hiring.approve') ? '/hiring/inbox' : permissions.includes('hiring.receive') ? '/hiring/received' : '/hiring/requests'}>Назад к очереди</Link>} 
    />
    
    {error && <div className="api-error-card"><strong>Действие не выполнено</strong><p>{error}</p></div>}
    
    <div className="hiring-main-title">ЗАЯВЛЕНИЕ НА НАЙМ</div>
    
    <div className="hiring-detail-grid">
      <section className="hiring-detail-main hiring-request-information">
        
        <header className="hiring-panel-header">
          <span><UserRound size={20} /></span>
          <div>
            <strong>Информация о кандидате</strong>
          </div>
        </header>
        
        <div className="hiring-summary-grid">
          <dl>
            <dt>Инициатор</dt>
            <dd>{request.initiatorName}</dd>
          </dl>
          <dl>
            <dt>ИИН</dt>
            <dd>{String(request.personal.iin ?? 'Недоступен')}</dd>
          </dl>
          <dl>
            <dt>Дата выхода</dt>
            <dd>{String(request.employmentData.startDate ?? '—')}</dd>
          </dl>
          <dl>
            <dt>Формат</dt>
            <dd>{String(request.employmentData.workArrangement ?? '—')}</dd>
          </dl>
        </div>
        
        <div className="hiring-information-section">
          <h3><BriefcaseBusiness size={17} />Параметры трудоустройства</h3>
          <div className="hiring-information-grid">
            <dl>
              <dt>Подразделение</dt>
              <dd>{String(request.employmentData.department ?? 'Не указано')}</dd>
            </dl>
            <dl>
              <dt>Должность</dt>
              <dd>{String(request.employmentData.position ?? 'Не указана')}</dd>
            </dl>
            <dl>
              <dt>Место работы</dt>
              <dd>{String(request.employmentData.workplace ?? 'Не указано')}</dd>
            </dl>
            <dl>
              <dt>График</dt>
              <dd>{String(request.employmentData.schedule ?? 'Не указан')}</dd>
            </dl>
            <dl>
              <dt>Тип занятости</dt>
              <dd>{String(request.employmentData.employmentType ?? 'Не указан')}</dd>
            </dl>
            <dl>
              <dt>Ставка</dt>
              <dd>{request.employmentData.fte ? `${String(request.employmentData.fte)} FTE` : 'Не указана'}</dd>
            </dl>
          </div>
        </div>
        
        <div className="hiring-information-section">
          <h3><GraduationCap size={17} />Образование и опыт</h3>
          <div className="hiring-information-grid cols-4">
            <dl>
              <dt>Уровень образования</dt>
              <dd>{String(request.educationData.educationLevel ?? 'Не указан')}</dd>
            </dl>
            <dl>
              <dt>Учебное заведение</dt>
              <dd>{String(request.educationData.institution ?? 'Не указано')}</dd>
            </dl>
            <dl>
              <dt>Специализация</dt>
              <dd>{String(request.educationData.specialization ?? 'Не указана')}</dd>
            </dl>
            <dl>
              <dt>Общий опыт</dt>
              <dd>{String(request.educationData.totalExperience ?? 'Не указан')}</dd>
            </dl>
          </div>
        </div>
      </section>

      <aside className="hiring-document-panel">
        <header className="hiring-panel-header">
          <span><FileText size={20} /></span>
          <div>
            <strong>Пакет документов</strong>
          </div>
        </header>

        <div className="hiring-files">
          {request.attachments.map((file) => (
            <a href={hiringRequestsApi.downloadUrl(id, file.versionId)} key={file.id}>
              <span>
                <strong>{file.originalFilename}</strong>
                <small>{file.category === 'identity' ? 'Удостоверение личности' : 'Диплом'} · {(file.sizeBytes / 1024 / 1024).toFixed(2)} МБ</small>
              </span>
              <Download size={16} />
            </a>
          ))}
        </div>

        {finalVersion && (
          <a className="open-app-button" href={hiringRequestsApi.downloadUrl(id, finalVersion, true)} target="_blank" rel="noreferrer">
            <FileText size={16} />Открыть заявление
          </a>
        )}
      </aside>
    </div>

    {/* Full-width Feedback and Decision History Container */}
    {(canApprove || canAcknowledge || (request.decisions && request.decisions.length > 0) || (permissions.includes('hiring.initiate') && request.status === 'final_approved') || (request.status === 'completed' && request.hiredEmployee)) && (
      <div className="hiring-bottom-feedback-container">
        
        {/* Decisions history / Timeline of comments */}
        {request.decisions && request.decisions.length > 0 && (
          <div className="hiring-decisions-history">
            <h4>История согласования</h4>
            <div className="decisions-timeline">
              {request.decisions.map((dec) => (
                <div key={dec.id} className={`timeline-item decision-${dec.decision}`}>
                  <div className="timeline-dot" />
                  <div className="timeline-content">
                    <header>
                      <strong>{dec.approverName}</strong>
                      <span>({dec.approverRole})</span>
                      <time>{formatDate(dec.decidedAt, locale, 'dd MMM yyyy, HH:mm')}</time>
                      <span className={`decision-badge decision-${dec.decision}`}>
                        {dec.decision === 'approve' ? 'Согласовано' : dec.decision === 'return' ? 'Возвращено' : 'Отклонено'}
                      </span>
                    </header>
                    {dec.comment && <p className="decision-comment">{dec.comment}</p>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Comment input & approval action panel */}
        {(canApprove || canAcknowledge) && (
          <div className="hiring-comment-action-panel">
            <div className="comment-input-area">
              <label htmlFor="hiring-comment-input">Комментарий к решению</label>
              <textarea 
                id="hiring-comment-input"
                value={comment} 
                onChange={(event) => setComment(event.target.value)} 
                placeholder="Добавьте пояснение к решению..." 
                className="non-resizable-comment"
              />
            </div>
            
            <div className="action-buttons-row">
              {canApprove ? (
                <>
                  <button disabled={action.isPending} className="approve-btn" onClick={() => action.mutate('approve')}>
                    <Check size={16} /> Согласовать
                  </button>
                  <button disabled={action.isPending} className="return-btn" onClick={() => action.mutate('return')}>
                    <Undo2 size={16} /> Вернуть
                  </button>
                  <button disabled={action.isPending} className="reject-btn" onClick={() => action.mutate('reject')}>
                    <X size={16} /> Отклонить
                  </button>
                </>
              ) : (
                <button disabled={action.isPending} className="approve-btn full-width" onClick={() => action.mutate('acknowledge')}>
                  <Check size={16} /> Подтвердить получение
                </button>
              )}
            </div>
          </div>
        )}

        {/* Initiate dispatch button */}
        {permissions.includes('hiring.initiate') && request.status === 'final_approved' && (
          <div className="hiring-dispatch-panel">
            <button disabled={action.isPending} className="primary-button" onClick={() => action.mutate('dispatch')}>
              <Send size={16} /> Отправить в бухгалтерию и IT
          </button>
          </div>
        )}

        {/* Created Employee info box */}
        {request.status === 'completed' && request.hiredEmployee && (
          <div className="hiring-employee-created-panel">
            <div className="lifecycle-action-title">
              <span><UserPlus size={18} /></span>
              <div>
                <strong>Сотрудник создан автоматически</strong>
                <small>Карточка сформирована после подтверждения бухгалтерии и IT</small>
              </div>
            </div>
            <div className="hired-employee-details">
              <dl>
                <dt>Табельный номер</dt>
                <dd>{request.hiredEmployee.employeeNumber}</dd>
              </dl>
              <dl>
                <dt>Корпоративный e-mail</dt>
                <dd>{request.hiredEmployee.corporateEmail ?? '—'}</dd>
              </dl>
            </div>
            <Link className="primary-button" style={{ alignSelf: 'flex-start' }} to={`/hr/employees/${request.hiredEmployee.id}?hired=1`}>
              Открыть профиль сотрудника
            </Link>
          </div>
        )}
      </div>
    )}
  </>;
}
