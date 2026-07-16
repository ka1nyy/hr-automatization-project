import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FileSignature, X } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Section } from '../../../shared/components';
import { formatDate } from '../../../shared/format';
import { useDeveloperStore } from '../../../shared/store';
import { hrRepository } from '../api';
import type { HrEmployee, TerminationCase } from '../model/types';

const caseStatusLabels: Record<string, string> = {
  hr_review: 'Проверка HR',
  legal_review: 'Юридическая проверка',
  signature: 'Подписание',
  registration: 'Регистрация приказа',
  offboarding: 'Офбординг',
  scheduled: 'Запланировано',
  returned: 'Возвращено на доработку',
  rejected: 'Отклонено',
  cancelled: 'Отменено',
  completed: 'Завершено'
};

const OPEN_STATUSES = new Set(['hr_review', 'legal_review', 'signature', 'registration', 'offboarding', 'scheduled', 'returned']);

const today = () => new Date().toISOString().slice(0, 10);

function InitiateDialog({ employee, onClose }: { employee: HrEmployee; onClose: () => void }) {
  const queryClient = useQueryClient();
  const reasons = useQuery({
    queryKey: ['termination-reasons', employee.unitId],
    queryFn: () => hrRepository.listTerminationReasons(employee.unitId)
  });
  const [reasonId, setReasonId] = useState('');
  const [requestedDate, setRequestedDate] = useState(today());
  const [legalBasis, setLegalBasis] = useState('');
  const initiate = useMutation({
    mutationFn: () =>
      hrRepository.initiateTermination({
        employeeId: employee.id,
        unitId: employee.unitId ?? '',
        reasonId,
        requestedDate,
        legalBasis
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['termination-cases'] });
      onClose();
    }
  });

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    initiate.mutate();
  };

  return <div className="dialog-backdrop">
    <section className="dialog hr-confirm-dialog" role="dialog" aria-modal="true" aria-label="Инициировать увольнение">
      <header><span>Инициировать увольнение</span><button type="button" className="icon-button" onClick={onClose} aria-label="Закрыть"><X size={18} /></button></header>
      <form onSubmit={submit}>
        <p>Запускается формальный маршрут: проверка HR{reasons.data?.find((item) => item.id === reasonId)?.legalReviewRequired ? ' → юридическая проверка' : ''} → подписание → регистрация приказа → офбординг.</p>
        <div className="field-grid">
          <label className="span-two">Основание (причина)<em>*</em>
            <select value={reasonId} onChange={(event) => setReasonId(event.target.value)} required>
              <option value="">{reasons.isLoading ? 'Загрузка…' : 'Выберите'}</option>
              {(reasons.data ?? []).map((reason) => <option key={reason.id} value={reason.id}>{reason.name}</option>)}
            </select>
          </label>
          <label>Желаемая дата<em>*</em><input type="date" value={requestedDate} onChange={(event) => setRequestedDate(event.target.value)} required /></label>
          <label className="span-two">Правовое основание<em>*</em><textarea value={legalBasis} onChange={(event) => setLegalBasis(event.target.value)} rows={3} placeholder="Статья ТК РК, заявление, соглашение сторон…" required /></label>
        </div>
        {initiate.error ? <div className="hr-attachment-error" role="alert">{String(initiate.error.message)}</div> : null}
        <footer>
          <button type="button" className="secondary-button" onClick={onClose}>Отмена</button>
          <button type="submit" className="primary-button" disabled={initiate.isPending}>{initiate.isPending ? 'Создаётся…' : 'Запустить маршрут'}</button>
        </footer>
      </form>
    </section>
  </div>;
}

function DecisionButtons({ current }: { current: TerminationCase }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState('');
  const act = useMutation({
    mutationFn: ({ decision, comment }: { decision: 'approve' | 'return' | 'reject'; comment: string }) =>
      hrRepository.decideTermination(current.id, decision, comment, current.revision),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['termination-cases'] }),
    onError: (mutationError) => setError(String(mutationError.message))
  });
  const withComment = (decision: 'return' | 'reject') => {
    const comment = window.prompt(decision === 'return' ? 'Причина возврата на доработку:' : 'Причина отклонения:');
    if (comment?.trim()) act.mutate({ decision, comment });
  };
  return <>
    <div className="hr-case-actions">
      <button type="button" className="primary-button" disabled={act.isPending} onClick={() => act.mutate({ decision: 'approve', comment: '' })}>Согласовать (HR)</button>
      <button type="button" className="secondary-button" disabled={act.isPending} onClick={() => withComment('return')}>Вернуть</button>
      <button type="button" className="secondary-button" disabled={act.isPending} onClick={() => withComment('reject')}>Отклонить</button>
    </div>
    {error && <div className="hr-attachment-error" role="alert">{error}</div>}
  </>;
}

export function TerminationSection({ employee }: { employee: HrEmployee }) {
  const locale = useDeveloperStore((state) => state.locale);
  const queryClient = useQueryClient();
  const [initiating, setInitiating] = useState(false);
  const [error, setError] = useState('');
  const cases = useQuery({
    queryKey: ['termination-cases', employee.id],
    queryFn: () => hrRepository.listTerminationCases(employee.id),
    retry: false
  });
  const cancel = useMutation({
    mutationFn: (current: TerminationCase) => {
      const reason = window.prompt('Причина отмены маршрута:');
      if (!reason?.trim()) return Promise.reject(new Error('Причина обязательна.'));
      return hrRepository.cancelTermination(current.id, current.revision, reason);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['termination-cases'] }),
    onError: (mutationError) => setError(String(mutationError.message))
  });

  // 403 means the persona has no termination visibility — hide the section.
  if (cases.error) return null;
  const items = cases.data ?? [];
  const openCase = items.find((item) => OPEN_STATUSES.has(item.status)) ?? null;
  const lastCase = openCase ?? items[0] ?? null;

  return <Section
    title="Увольнение (маршрут)"
    meta={openCase ? 'Идёт формальный процесс' : 'Формальный процесс модуля увольнений'}
    className="hr-termination-section"
  >
    {lastCase ? <div className="hr-case-card">
      <div>
        <strong>{caseStatusLabels[lastCase.status] ?? lastCase.status}</strong>
        <small>
          Желаемая дата: {formatDate(lastCase.requested_date, locale)}
          {lastCase.effective_date ? ` · Дата увольнения: ${formatDate(lastCase.effective_date, locale)}` : ''}
        </small>
      </div>
      {lastCase.status === 'hr_review' && <DecisionButtons current={lastCase} />}
      {openCase && <button type="button" className="secondary-button" disabled={cancel.isPending} onClick={() => cancel.mutate(openCase)}>Отменить маршрут</button>}
    </div> : <p className="hr-empty-note">Активного процесса увольнения нет.</p>}
    {!openCase && <button type="button" className="secondary-button" onClick={() => setInitiating(true)}><FileSignature size={16} /> Инициировать увольнение</button>}
    {error && <div className="hr-attachment-error" role="alert">{error}</div>}
    {initiating && <InitiateDialog employee={employee} onClose={() => setInitiating(false)} />}
  </Section>;
}
