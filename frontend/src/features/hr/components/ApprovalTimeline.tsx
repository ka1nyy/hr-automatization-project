import { Check, Clock3, RotateCcw, X } from 'lucide-react';
import type { HiringRequest } from '../api/hiringRequests';

export function ApprovalTimeline({ request }: { request: HiringRequest }) {
  return <ol className="hiring-approval-timeline">
    {request.approvalStages.map((stage) => {
      const decision = [...request.decisions].reverse().find((item) => item.stageNumber === stage.stageNumber);
      const current = request.status === 'under_review' && request.currentStage === stage.stageNumber;
      const state = decision?.decision ?? (current ? 'current' : 'pending');
      return <li className={state} key={stage.code}>
        <span>{decision?.decision === 'approve' ? <Check size={16} /> : decision?.decision === 'reject' ? <X size={16} /> : decision?.decision === 'return' ? <RotateCcw size={16} /> : <Clock3 size={16} />}</span>
        <div><small>Этап {stage.stageNumber}</small><strong>{stage.name}</strong><p>{decision ? `${decision.approverName} · ${new Date(decision.decidedAt).toLocaleString('ru-RU')}` : current ? 'Ожидает вашего решения' : 'Ожидает предыдущий этап'}</p>{decision?.comment && <blockquote>{decision.comment}</blockquote>}</div>
      </li>;
    })}
  </ol>;
}
