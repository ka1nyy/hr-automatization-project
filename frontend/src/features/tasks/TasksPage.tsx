import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, CheckCircle2, ChevronRight, Clock3, Filter, Hand, Inbox, Search, UserRound } from 'lucide-react';
import { repositories } from '../../repositories';
import { EmptyState, PageHeader, QueryState } from '../../shared/components';
import { formatDate } from '../../shared/format';
import { PermissionGate } from '../../shared/permissions';
import { useDeveloperStore } from '../../shared/store';
import { useDepartmentContext } from '../hr/context/DepartmentContext';

export default function TasksPage() {
  const locale = useDeveloperStore((state) => state.locale);
  const department = useDepartmentContext();
  const [filter, setFilter] = useState('active');
  const queryClient = useQueryClient();
  const result = useQuery({ queryKey: ['tasks'], queryFn: () => repositories.tasks.list() });
  const mutation = useMutation({ mutationFn: ({ id, action }: { id: string; action: 'claim' | 'complete' }) => action === 'claim' ? repositories.tasks.claim(id) : repositories.tasks.complete(id), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks'] }) });
  const tasks = (result.data ?? []).filter((task) => filter === 'all' || (filter === 'active' && task.state !== 'completed') || task.state === filter);
  return <>
    <PageHeader eyebrow={`${department.departmentCode} · Моя работа`} title={department.isHrWorkspace ? 'Задачи HR' : 'Единый центр задач'} description={department.isHrWorkspace ? 'Личные и доступные кадровые задачи из общих корпоративных процессов.' : 'Личные и доступные задачи всех корпоративных процессов в одной очереди.'} actions={<button className="secondary-button"><Filter size={16} /> Настроить представление</button>} />
    <div className="task-workspace">
      <aside className="task-filters"><button className={filter === 'active' ? 'active' : ''} onClick={() => setFilter('active')}><Inbox size={17} /> Активные <b>{result.data?.filter((t) => t.state !== 'completed').length ?? 0}</b></button><button className={filter === 'available' ? 'active' : ''} onClick={() => setFilter('available')}><Hand size={17} /> Доступные <b>{result.data?.filter((t) => t.state === 'available').length ?? 0}</b></button><button className={filter === 'claimed' ? 'active' : ''} onClick={() => setFilter('claimed')}><UserRound size={17} /> Назначенные мне</button><button className={filter === 'overdue' ? 'active' : ''} onClick={() => setFilter('overdue')}><Clock3 size={17} /> Просроченные</button><button className={filter === 'completed' ? 'active' : ''} onClick={() => setFilter('completed')}><CheckCircle2 size={17} /> Завершённые</button></aside>
      <div className="task-list-panel"><div className="task-list-toolbar"><label className="field-search"><Search size={16} /><input placeholder="Поиск по задачам" /></label><span>{tasks.length} задач</span></div>
        {result.isLoading ? <QueryState /> : result.error ? <QueryState error={result.error} retry={() => result.refetch()} /> : tasks.length === 0 ? <EmptyState title="Очередь пуста" text="Для выбранного представления задач нет." /> : <div className="task-list">{tasks.map((task) => <article key={task.id}><span className={`priority-line priority-${task.priority}`} /><div className="task-state-icon">{task.state === 'completed' ? <Check size={17} /> : <span />}</div><div className="task-copy"><span><b>{task.role}</b><small>{task.process}</small></span><h2>{task.title}</h2><p>{task.documentNumber} · {task.department}</p><footer><span className={task.state === 'overdue' ? 'text-coral' : ''}><Clock3 size={14} /> до {formatDate(task.dueDate, locale)}</span>{task.assignee && <span><UserRound size={14} /> {task.assignee}</span>}</footer></div><div className="task-actions"><PermissionGate permission="task.claim">{task.state === 'available' && <button className="secondary-button" onClick={() => mutation.mutate({ id: task.id, action: 'claim' })}>Взять</button>}</PermissionGate><PermissionGate permission="task.complete">{task.state === 'claimed' && <button className="primary-button" onClick={() => mutation.mutate({ id: task.id, action: 'complete' })}><Check size={15} /> Завершить</button>}</PermissionGate><button className="icon-button"><ChevronRight size={18} /></button></div></article>)}</div>}
      </div>
    </div>
  </>;
}
