import { useQuery } from '@tanstack/react-query';
import { ArrowRight, FileSignature } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Section } from '../../../shared/components';
import { formatDate } from '../../../shared/format';
import { useDeveloperStore } from '../../../shared/store';
import { hrRepository } from '../api';
import type { HrEmployee } from '../model/types';

const caseStatusLabels: Record<string, string> = {
  hr_review: 'На согласовании',
  economic_review: 'На согласовании',
  legal_review: 'На согласовании',
  signature: 'На подписании',
  registration: 'Регистрация приказа',
  offboarding: 'Офбординг',
  scheduled: 'Увольнение запланировано',
  returned: 'Возвращено на доработку',
  rejected: 'Отклонено',
  cancelled: 'Отменено',
  completed: 'Трудовые отношения завершены'
};

const OPEN_STATUSES = new Set([
  'hr_review',
  'economic_review',
  'legal_review',
  'signature',
  'registration',
  'offboarding',
  'scheduled',
  'returned'
]);

export function TerminationSection({ employee }: { employee: HrEmployee }) {
  const locale = useDeveloperStore((state) => state.locale);
  const cases = useQuery({
    queryKey: ['termination-cases', employee.id],
    queryFn: () => hrRepository.listTerminationCases(employee.id),
    retry: false
  });

  if (cases.error) return null;
  const items = cases.data ?? [];
  const openCase = items.find((item) => OPEN_STATUSES.has(item.status)) ?? null;
  const lastCase = openCase ?? items[0] ?? null;

  return <Section
    title="Увольнение"
    meta={openCase ? 'Активный кадровый процесс' : 'Прекращение трудовых отношений'}
    className="hr-termination-section"
  >
    {lastCase ? <div className="hr-case-card">
      <div>
        <strong>{caseStatusLabels[lastCase.status] ?? lastCase.status}</strong>
        <small>
          Заявленная дата: {formatDate(lastCase.requested_date, locale)}
          {lastCase.effective_date ? ` · Дата увольнения: ${formatDate(lastCase.effective_date, locale)}` : ''}
        </small>
      </div>
      <Link className="secondary-button" to={`/hr/terminations/${lastCase.id}`}>
        Открыть заявление <ArrowRight size={16} />
      </Link>
    </div> : <div className="termination-profile-empty">
      <span><FileSignature size={20} /></span>
      <div><strong>Активного заявления нет</strong><p>Увольнение запускается только через формальный маршрут согласования.</p></div>
    </div>}
    {!openCase && <Link className="secondary-button" to={`/hr/terminations?create=true&employee=${employee.id}`}>
      <FileSignature size={16} /> Начать увольнение
    </Link>}
  </Section>;
}
