import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Ban, X } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Section } from '../../../shared/components';
import { formatDate } from '../../../shared/format';
import { useDeveloperStore } from '../../../shared/store';
import { hrRepository } from '../api';
import type { EmployeeAbsence } from '../model/types';

const typeLabels: Record<EmployeeAbsence['absenceType'], string> = {
  vacation: 'Отпуск',
  sick_leave: 'Больничный',
  business_trip: 'Командировка',
  day_off: 'Отгул'
};

const statusLabels: Record<EmployeeAbsence['status'], string> = {
  scheduled: 'Запланировано',
  active: 'Идёт',
  completed: 'Завершено',
  cancelled: 'Отменено'
};

function CancelAbsenceDialog({ employeeId, absence, onClose }: { employeeId: string; absence: EmployeeAbsence; onClose: () => void }) {
  const locale = useDeveloperStore((state) => state.locale);
  const [reason, setReason] = useState('');
  const queryClient = useQueryClient();
  const cancel = useMutation({
    mutationFn: () =>
      hrRepository.invokeEmployeeFunction(employeeId, 'employee.absence_cancel', {
        absenceId: absence.id,
        reason,
        revision: absence.revision
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['employee-absences'] }),
        queryClient.invalidateQueries({ queryKey: ['hr'] })
      ]);
      onClose();
    }
  });

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    cancel.mutate();
  };

  return <div className="dialog-backdrop">
    <section className="dialog hr-confirm-dialog" role="dialog" aria-modal="true" aria-label="Отменить отсутствие">
      <header><span>Отменить отсутствие</span><button type="button" className="icon-button" onClick={onClose} aria-label="Закрыть"><X size={18} /></button></header>
      <form onSubmit={submit}>
        <p>{typeLabels[absence.absenceType]} · {formatDate(absence.dateFrom, locale, 'dd MMM')} — {formatDate(absence.dateTo, locale, 'dd MMM yyyy')}</p>
        <div className="field-grid">
          <label className="span-two">Причина отмены<em>*</em><textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={3} required /></label>
        </div>
        {cancel.error ? <div className="hr-attachment-error" role="alert">{String(cancel.error.message)}</div> : null}
        <footer>
          <button type="button" className="secondary-button" onClick={onClose}>Закрыть</button>
          <button type="submit" className="primary-button" disabled={cancel.isPending}>{cancel.isPending ? 'Отменяется…' : 'Отменить отсутствие'}</button>
        </footer>
      </form>
    </section>
  </div>;
}

export function EmployeeAbsencesSection({ employeeId }: { employeeId: string }) {
  const locale = useDeveloperStore((state) => state.locale);
  const absences = useQuery({
    queryKey: ['employee-absences', employeeId],
    queryFn: () => hrRepository.listAbsences(employeeId)
  });
  const functions = useQuery({
    queryKey: ['employee-functions', employeeId],
    queryFn: () => hrRepository.listEmployeeFunctions(employeeId)
  });
  const [cancelling, setCancelling] = useState<EmployeeAbsence | null>(null);
  const canCancel = (functions.data ?? []).some((item) => item.key === 'employee.absence_cancel');
  const balance = absences.data?.vacationBalance;
  const items = absences.data?.items ?? [];

  return <Section
    title="Отсутствия"
    meta={balance ? `Отпуск ${balance.year}: осталось ${balance.remaining} из ${balance.entitlement} дней` : undefined}
  >
    {items.length === 0
      ? <p className="hr-empty-note">Отсутствий не зарегистрировано.</p>
      : <div className="hr-request-list">
        {items.map((absence) => <article key={absence.id}>
          <div>
            <strong>{typeLabels[absence.absenceType]}</strong>
            <small>
              {formatDate(absence.dateFrom, locale, 'dd MMM')} — {formatDate(absence.dateTo, locale, 'dd MMM yyyy')} · {absence.days} дн.
              {absence.details ? ` · ${absence.details}` : ''}
            </small>
          </div>
          <span className={`hr-absence-status hr-absence-${absence.status}`}>{statusLabels[absence.status]}</span>
          {canCancel && (absence.status === 'scheduled' || absence.status === 'active') && (
            <button type="button" className="icon-button" title="Отменить отсутствие" aria-label="Отменить отсутствие" onClick={() => setCancelling(absence)}>
              <Ban size={15} />
            </button>
          )}
        </article>)}
      </div>}
    {cancelling && <CancelAbsenceDialog employeeId={employeeId} absence={cancelling} onClose={() => setCancelling(null)} />}
  </Section>;
}
