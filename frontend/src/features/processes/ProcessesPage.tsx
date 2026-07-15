import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertOctagon, CheckCircle2, ChevronRight, CircleDot, GitBranch, History, Play, RefreshCw, Search, ShieldAlert } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { repositories } from '../../repositories';
import { PageHeader, QueryState, Section } from '../../shared/components';
import { formatDate } from '../../shared/format';
import { useDeveloperStore } from '../../shared/store';
import { useDepartmentContext } from '../hr/context/DepartmentContext';
import { hrRepository } from '../hr/api';

export default function ProcessesPage() {
  const locale = useDeveloperStore((state) => state.locale);
  const department = useDepartmentContext();
  const queryClient = useQueryClient();
  const result = useQuery({ queryKey: ['processes'], queryFn: () => repositories.workflows.listDefinitions() });
  const [searchParams, setSearchParams] = useSearchParams();
  const querySelected = searchParams.get('id');
  const [search, setSearch] = useState('');

  const retry = useMutation({ mutationFn: (id: string) => repositories.workflows.retryIncident(id), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['processes'] }) });
  const processes = department.isHrWorkspace ? result.data?.filter((item) => item.owner === department.departmentName) : result.data;
  
  const selected = querySelected || (department.isHrWorkspace ? 'p-hr-leave' : 'p-incoming');
  const setSelected = (id: string) => setSearchParams({ id });

  const incoming = useQuery({ queryKey: ['incoming'], queryFn: () => repositories.correspondence.listIncoming() });
  const leaves = useQuery({ queryKey: ['hr', 'leave'], queryFn: () => hrRepository.listLeaveRequests() });

  if (result.isLoading) return <QueryState />;
  if (result.error || !processes) return <QueryState error={result.error ?? new Error('Нет определений процессов')} retry={() => result.refetch()} />;

  const process = processes.find((item) => item.id === selected) ?? processes[0];
  if (!process) return <QueryState error={new Error('Процесс не найден')} retry={() => result.refetch()} />;

  // Filter processes catalog by search text
  const filteredProcesses = processes.filter((item) => item.name.toLowerCase().includes(search.toLowerCase()));

  // Active instances for the selected process
  let instances: Array<{ id: string; number: string; title: string; step: string; status: string; date: string }> = [];
  if (process.id === 'p-hr-leave' && leaves.data) {
    instances = leaves.data.map(item => ({
      id: item.id,
      number: item.documentNumber,
      title: item.employeeName,
      step: item.workflowStep,
      status: item.status,
      date: item.startDate
    }));
  } else if (process.id === 'p-incoming' && incoming.data) {
    instances = incoming.data.map(item => ({
      id: item.id,
      number: item.number,
      title: item.sender,
      step: item.workflowStep,
      status: item.status,
      date: item.dueDate
    }));
  }

  return <>
    <PageHeader eyebrow={`${department.departmentCode} · Workflow Gateway`} title={department.isHrWorkspace ? 'Процессы' : 'Центр процессов'} />
    <div className="process-summary"><article><span className="tone-violet"><GitBranch size={18} /></span><div><strong>{processes.length}</strong><small>определения</small></div></article><article><span className="tone-teal"><Play size={18} /></span><div><strong>{processes.reduce((sum, item) => sum + item.activeInstances, 0)}</strong><small>активных экземпляра</small></div></article><article><span className="tone-gold"><History size={18} /></span><div><strong>{processes.filter((item) => item.state === 'published').length}</strong><small>версий опубликовано</small></div></article><article><span className="tone-coral"><AlertOctagon size={18} /></span><div><strong>{processes.filter((p) => p.state === 'incident').length}</strong><small>инцидент</small></div></article></div>
    <div className="process-layout">
      <Section title="Каталог процессов" meta={`${processes.length} определения`}><label className="field-search process-search"><Search size={16} /><input placeholder="Найти процесс" value={search} onChange={(e) => setSearch(e.target.value)} /></label><div className="process-list">{filteredProcesses.map((item) => <button className={selected === item.id ? 'active' : ''} onClick={() => setSelected(item.id)} key={item.id}><span className={`process-symbol ${item.state}`}><GitBranch size={17} /></span><span><strong>{item.name}</strong><small>v{item.version} · {item.activeInstances} экземпляров</small></span><span className={`state-label state-${item.state}`}>{item.state === 'published' ? 'Опубликован' : item.state === 'draft' ? 'Черновик' : 'Инцидент'}</span><ChevronRight size={16} /></button>)}</div></Section>
      <div className="process-detail">
        <Section title={process.name} meta={`Версия ${process.version}`}><div className="process-meta"><span><small>Владелец</small><strong>{process.owner}</strong></span><span><small>Обновлён</small><strong>{formatDate(process.updatedAt, locale)}</strong></span><span><small>Экземпляры</small><strong>{process.activeInstances} активных</strong></span><span><small>Статус</small><strong className={`text-${process.state === 'incident' ? 'coral' : 'emerald'}`}>{process.state}</strong></span></div><div className="bpmn-canvas" aria-label="Текстовое представление процесса"><div className="lane-label">СЕКРЕТАРИАТ</div><div className="process-nodes">{process.steps.map((step, index) => <div key={step}><span className={index === 0 ? 'event-node' : 'task-node'}>{index === 0 ? <CircleDot size={18} /> : step}</span>{index < process.steps.length - 1 && <i />}</div>)}</div><div className="lane-label bottom">КОРПОРАТИВНЫЙ ПРОЦЕСС</div></div><div className="text-alternative"><strong>Текстовый маршрут:</strong>{process.steps.join(' → ')}</div></Section>
        {process.state === 'incident' ? <Section title="Активный инцидент" meta="Требует внимания" className="incident-panel"><div className="incident-body"><span><ShieldAlert size={22} /></span><div><strong>Ошибка выполнения процесса</strong><p>Экземпляр приостановлен и может быть безопасно запущен повторно.</p></div><button className="primary-button" onClick={() => retry.mutate(process.id)} disabled={retry.isPending}><RefreshCw size={16} /> {retry.isPending ? 'Повтор…' : 'Повторить'}</button></div></Section> : <Section title="Проверка маршрута" meta="Последняя проверка: успешно"><div className="test-result"><CheckCircle2 size={22} /><span><strong>Маршрут валиден</strong><small>Все процессные роли назначены · SLA задан · форма доступна</small></span></div></Section>}
        
        <Section title="Активные экземпляры" meta={`${instances.length} запущено`}>
          <div className="queue-table borderless" style={{ display: 'grid', width: '100%' }}>
            <div className="table-head">
              <span>Документ</span>
              <span>Инициатор / Отправитель</span>
              <span>Текущий шаг</span>
              <span>Срок / Дата</span>
              <span />
            </div>
            {instances.map((inst) => {
              const to = process.id === 'p-incoming' ? `/correspondence/incoming/${inst.id}` : (process.id === 'p-hr-leave' ? `/hr/leave` : '#');
              return (
                <Link to={to} className="table-row" key={inst.id} style={{ color: 'inherit', textDecoration: 'none' }}>
                  <span><strong>{inst.number}</strong></span>
                  <span>{inst.title}</span>
                  <span><i className="status-dot status-execution" />{inst.step}</span>
                  <span>{formatDate(inst.date, locale)}</span>
                  <ChevronRight size={15} />
                </Link>
              );
            })}
          </div>
        </Section>
      </div>
    </div>
  </>;
}
