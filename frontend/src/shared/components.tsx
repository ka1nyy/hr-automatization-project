import type { ComponentType, PropsWithChildren, ReactNode } from 'react';
import { AlertTriangle, ArrowUpRight, CalendarCheck2, FileSignature, FileX2, RefreshCw } from 'lucide-react';

/**
 * Shared «Всего записей / Требуют действия / Завершено» strip for the workforce
 * process workspaces. Mirrors the markup WorkforceProcessPage renders for отпуска
 * and увольнения so every Персонал process reads the same.
 */
export function ProcessMetrics({ icon: Icon, total, actionable, completed }: { icon: ComponentType<{ size?: number }>; total: number; actionable: number; completed: number }) {
  return <div className="planned-metric-grid">
    <article><span><Icon size={20} /></span><div><small>Всего записей</small><strong>{total}</strong><em>из backend</em></div></article>
    <article><span><FileSignature size={20} /></span><div><small>Требуют действия</small><strong>{actionable}</strong><em>для текущей роли</em></div></article>
    <article><span><CalendarCheck2 size={20} /></span><div><small>Завершено</small><strong>{completed}</strong><em>маршрут пройден</em></div></article>
  </div>;
}

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description?: string; actions?: ReactNode }) {
  return <header className="page-header"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1>{description && <p>{description}</p>}</div>{actions && <div className="page-actions">{actions}</div>}</header>;
}

export function Section({ title, meta, children, className = '' }: PropsWithChildren<{ title: string; meta?: string; className?: string }>) {
  return <section className={`panel ${className}`}><header className="panel-header"><h2>{title}</h2>{meta && <span>{meta}</span>}</header>{children}</section>;
}

export function QueryState({ error, retry }: { error?: Error | null; retry?: () => void }) {
  if (!error) return <div className="page-loading"><span /><span /><span /></div>;
  return <div className="empty-state"><AlertTriangle size={28} /><h2>Не удалось загрузить данные</h2><p>{error.message}</p>{retry && <button className="secondary-button" onClick={retry}><RefreshCw size={16} /> Повторить</button>}</div>;
}

export function EmptyState({ title, text }: { title: string; text: string }) {
  return <div className="empty-state"><FileX2 size={28} /><h2>{title}</h2><p>{text}</p></div>;
}

export function LinkArrow() { return <ArrowUpRight size={15} />; }
