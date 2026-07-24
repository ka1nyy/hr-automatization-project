import { useMemo, useState, type ReactNode } from 'react';
import { CheckCircle2, CircleDot, Lock, ShieldCheck } from 'lucide-react';
import type { DecisionGate, RegistryDocument, RoleDuty, StatusState, WorkflowStage } from './data/types';

/** Segmented tab control used to switch between reference views on a page. */
export function SegmentTabs({ tabs, active, onChange }: { tabs: Array<{ id: string; label: string; count?: number }>; active: string; onChange: (id: string) => void }) {
  return (
    <div className="wf-tabs" role="tablist">
      {tabs.map((tab) => (
        <button key={tab.id} role="tab" aria-selected={active === tab.id} className={active === tab.id ? 'active' : ''} onClick={() => onChange(tab.id)}>
          {tab.label}
          {typeof tab.count === 'number' && <b>{tab.count}</b>}
        </button>
      ))}
    </div>
  );
}

export function MetricRow({ items }: { items: Array<{ label: string; value: ReactNode; hint?: string; tone?: string }> }) {
  return (
    <div className="wf-metric-row">
      {items.map((item, index) => (
        <article key={index} className={item.tone ? `tone-${item.tone}` : ''}>
          <strong>{item.value}</strong>
          <span>{item.label}</span>
          {item.hint && <small>{item.hint}</small>}
        </article>
      ))}
    </div>
  );
}

/** Phased vertical rail of workflow stages with a clickable focus. */
export function StageTimeline({ stages }: { stages: WorkflowStage[] }) {
  const [focus, setFocus] = useState(stages[0]?.index ?? 0);
  const phases = useMemo(() => {
    const order: string[] = [];
    for (const stage of stages) if (!order.includes(stage.phase)) order.push(stage.phase);
    return order.map((phase) => ({ phase, stages: stages.filter((stage) => stage.phase === phase) }));
  }, [stages]);
  return (
    <div className="wf-timeline">
      {phases.map((group) => (
        <div className="wf-phase" key={group.phase}>
          <div className="wf-phase-label"><span />{group.phase}</div>
          <div className="wf-stage-list">
            {group.stages.map((stage) => (
              <button key={stage.index} className={`wf-stage ${focus === stage.index ? 'active' : ''}`} onClick={() => setFocus(stage.index)}>
                <span className="wf-stage-index">{stage.index}</span>
                <span className="wf-stage-body">
                  <strong>{stage.title}</strong>
                  <small>{stage.owner}</small>
                  <p>{stage.outcome}</p>
                </span>
                <span className="wf-stage-sla">{stage.sla}</span>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function RoleMatrix({ roles }: { roles: RoleDuty[] }) {
  return (
    <div className="wf-table-scroll">
      <table className="wf-table">
        <thead><tr><th>Роль</th><th>Ответственность</th><th>Запрет</th></tr></thead>
        <tbody>
          {roles.map((role) => (
            <tr key={role.role}>
              <td className="wf-strong">{role.role}</td>
              <td>{role.responsibility}</td>
              <td className="wf-muted-cell"><Lock size={13} /> {role.restriction}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function GateList({ gates }: { gates: DecisionGate[] }) {
  return (
    <div className="wf-gate-list">
      {gates.map((gate) => (
        <article key={gate.code} className="wf-gate">
          <span className="wf-gate-code">{gate.code}</span>
          <div><strong>{gate.question}</strong><p>{gate.action}</p></div>
        </article>
      ))}
    </div>
  );
}

export function StatusBoard({ statuses }: { statuses: StatusState[] }) {
  return (
    <div className="wf-status-grid">
      {statuses.map((status) => (
        <article key={status.code} className="wf-status-card">
          <header><CircleDot size={14} /><code>{status.code}</code></header>
          <strong>{status.meaning}</strong>
          <small>{status.owner}</small>
          <p><ShieldCheck size={12} /> {status.guard}</p>
        </article>
      ))}
    </div>
  );
}

export function DocumentRegistry({ documents }: { documents: RegistryDocument[] }) {
  return (
    <div className="wf-doc-list">
      {documents.map((doc) => (
        <article key={doc.code} className="wf-doc">
          <span className="wf-doc-code">{doc.code}</span>
          <div className="wf-doc-body">
            <strong>{doc.title}</strong>
            <small>Готовит: {doc.preparedBy}</small>
          </div>
          <div className="wf-doc-sign"><CheckCircle2 size={13} />{doc.signedBy}</div>
        </article>
      ))}
    </div>
  );
}

/** Generic reference table for arbitrary column/row data. */
export function ReferenceTable<T>({ columns, rows, strongFirst = true }: { columns: Array<{ key: keyof T; label: string }>; rows: T[]; strongFirst?: boolean }) {
  return (
    <div className="wf-table-scroll">
      <table className="wf-table">
        <thead><tr>{columns.map((column) => <th key={String(column.key)}>{column.label}</th>)}</tr></thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((column, columnIndex) => (
                <td key={String(column.key)} className={strongFirst && columnIndex === 0 ? 'wf-strong' : ''}>{row[column.key] as ReactNode}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Coloured callout that transcribes a governing rule from the regulation. */
export function RuleCallout({ children }: { children: ReactNode }) {
  return <div className="wf-rule"><ShieldCheck size={16} /><p>{children}</p></div>;
}
