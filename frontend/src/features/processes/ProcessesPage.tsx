import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertOctagon, CheckCircle2, ChevronRight, CircleDot, GitBranch, History, Play, RefreshCw, Search, ShieldAlert } from 'lucide-react';
import { repositories } from '../../repositories';
import { PageHeader, QueryState, Section } from '../../shared/components';
import { formatDate } from '../../shared/format';
import { PermissionGate } from '../../shared/permissions';
import { useDeveloperStore } from '../../shared/store';
import { useDepartmentContext } from '../hr/context/DepartmentContext';

export default function ProcessesPage() {
  const locale = useDeveloperStore((state) => state.locale);
  const department = useDepartmentContext();
  const queryClient = useQueryClient();
  const result = useQuery({ queryKey: ['processes'], queryFn: () => repositories.workflows.listDefinitions() });
  const [selected, setSelected] = useState(department.isHrWorkspace ? 'p-hr-leave' : 'p-incoming');
  const retry = useMutation({ mutationFn: (id: string) => repositories.workflows.retryIncident(id), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['processes'] }) });
  const processes = department.isHrWorkspace ? result.data?.filter((item) => item.owner === department.departmentName) : result.data;
  const process = processes?.find((item) => item.id === selected) ?? processes?.[0];
  if (result.isLoading) return <QueryState />;
  if (result.error || !processes || !process) return <QueryState error={result.error ?? new Error('Нет определений процессов')} retry={() => result.refetch()} />;
  return <>
    <PageHeader eyebrow={`${department.departmentCode} · Workflow Gateway`} title={department.isHrWorkspace ? 'Процессы HR' : 'Центр процессов'} description={department.isHrWorkspace ? 'Активные кадровые маршруты, согласования и состояния исполнения.' : 'Определения, версии, активные экземпляры и инциденты корпоративных процессов.'} actions={<PermissionGate permission="workflow.definition.edit"><button className="primary-button"><GitBranch size={16} /> Новая версия</button></PermissionGate>} />
    <div className="process-summary"><article><span className="tone-violet"><GitBranch size={18} /></span><div><strong>{processes.length}</strong><small>определения</small></div></article><article><span className="tone-teal"><Play size={18} /></span><div><strong>{processes.reduce((sum, item) => sum + item.activeInstances, 0)}</strong><small>активных экземпляра</small></div></article><article><span className="tone-gold"><History size={18} /></span><div><strong>{processes.filter((item) => item.state === 'published').length}</strong><small>версий опубликовано</small></div></article><article><span className="tone-coral"><AlertOctagon size={18} /></span><div><strong>{processes.filter((p) => p.state === 'incident').length}</strong><small>инцидент</small></div></article></div>
    <div className="process-layout">
      <Section title="Каталог процессов" meta={`${processes.length} определения`}><label className="field-search process-search"><Search size={16} /><input placeholder="Найти процесс" /></label><div className="process-list">{processes.map((item) => <button className={selected === item.id ? 'active' : ''} onClick={() => setSelected(item.id)} key={item.id}><span className={`process-symbol ${item.state}`}><GitBranch size={17} /></span><span><strong>{item.name}</strong><small>v{item.version} · {item.activeInstances} экземпляров</small></span><span className={`state-label state-${item.state}`}>{item.state === 'published' ? 'Опубликован' : item.state === 'draft' ? 'Черновик' : 'Инцидент'}</span><ChevronRight size={16} /></button>)}</div></Section>
      <div className="process-detail">
        <Section title={process.name} meta={`Версия ${process.version}`}><div className="process-meta"><span><small>Владелец</small><strong>{process.owner}</strong></span><span><small>Обновлён</small><strong>{formatDate(process.updatedAt, locale)}</strong></span><span><small>Экземпляры</small><strong>{process.activeInstances} активных</strong></span><span><small>Статус</small><strong className={`text-${process.state === 'incident' ? 'coral' : 'emerald'}`}>{process.state}</strong></span></div><div className="bpmn-canvas" aria-label="Текстовое представление процесса"><div className="lane-label">СЕКРЕТАРИАТ</div><div className="process-nodes">{process.steps.map((step, index) => <div key={step}><span className={index === 0 ? 'event-node' : 'task-node'}>{index === 0 ? <CircleDot size={18} /> : step}</span>{index < process.steps.length - 1 && <i />}</div>)}</div><div className="lane-label bottom">КОРПОРАТИВНЫЙ ПРОЦЕСС</div></div><div className="text-alternative"><strong>Текстовый маршрут:</strong>{process.steps.join(' → ')}</div></Section>
        {process.state === 'incident' ? <Section title="Активный инцидент" meta="INC-2026-0048" className="incident-panel"><div className="incident-body"><span><ShieldAlert size={22} /></span><div><strong>NumberingServiceUnavailable</strong><p>Не удалось получить исходящий регистрационный номер после 3 попыток. Экземпляр приостановлен на шаге «Нумерация».</p><small>Переменные: documentId=out-729 · retryCount=3 · processVersion=6</small></div><button className="primary-button" onClick={() => retry.mutate(process.id)} disabled={retry.isPending}><RefreshCw size={16} /> {retry.isPending ? 'Повтор…' : 'Повторить в mock'}</button></div></Section> : <Section title="Проверка маршрута" meta="Последний запуск: успешно"><div className="test-result"><CheckCircle2 size={22} /><span><strong>Маршрут валиден</strong><small>Все процессные роли назначены · SLA задан · форма доступна</small></span><button className="secondary-button"><Play size={15} /> Запустить тест</button></div></Section>}
      </div>
    </div>
  </>;
}
