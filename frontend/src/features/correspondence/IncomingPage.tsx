import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CalendarDays, Download, LayoutGrid, List, Plus, Search, SlidersHorizontal } from 'lucide-react';
import { Link } from 'react-router-dom';
import { repositories } from '../../repositories';
import { EmptyState, PageHeader, QueryState } from '../../shared/components';
import { formatDate, statusLabels } from '../../shared/format';
import { useDeveloperStore } from '../../shared/store';
import { useDepartmentContext } from '../hr/context/DepartmentContext';

const departmentsList = [
  { name: 'Руководство', label: 'Председатель Правления' },
  { name: 'Департамент документооборота и управления персоналом', label: 'Кадры и ДО' },
  { name: 'Департамент инвестиций', label: 'Инвестиции' },
  { name: 'Департамент кредитования', label: 'Кредитование' },
  { name: 'Департамент активов', label: 'Активы' },
  { name: 'Департамент строительства', label: 'Строительство' },
  { name: 'Департамент стабильности фонда', label: 'Стабильность фонда' },
  { name: 'Департамент экономического планирования', label: 'Экономика' },
  { name: 'Юридический департамент', label: 'Юридический' },
  { name: 'Бухгалтерия', label: 'Бухгалтерия' }
];

function normalizeDept(name: string): string {
  if (!name) return '';
  let n = name.toLowerCase();
  n = n.replace('департамент ', '');
  if (n.startsWith('инвестиц')) return 'инвестиции';
  if (n.startsWith('актив')) return 'активы';
  if (n.startsWith('строитель')) return 'строительство';
  if (n.startsWith('экономическ')) return 'экономическое планирование';
  if (n.startsWith('управления персоналом') || n.startsWith('документооборота')) return 'управление персоналом';
  if (n.includes('руководство') || n.includes('председатель') || n.includes('правления')) return 'руководство';
  return n;
}

export default function IncomingPage() {
  const locale = useDeveloperStore((state) => state.locale);
  const department = useDepartmentContext();
  
  // Standard filters
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [activeTab, setActiveTab] = useState('external');
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');

  // Filters state (shared in the side drawer)
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [confidentialityFilter, setConfidentialityFilter] = useState('all');
  
  // Right Drawer toggle
  const [isFiltersDrawerOpen, setIsFiltersDrawerOpen] = useState(false);

  const result = useQuery({ queryKey: ['incoming'], queryFn: () => repositories.correspondence.listIncoming() });

  const filtered = useMemo(() => {
    return (result.data ?? []).filter((item) => {
      // Tab filter
      let matchesTab = true;
      if (activeTab === 'external') {
        matchesTab = item.channel !== 'Внутренняя система';
      } else if (activeTab !== 'all') {
        matchesTab = normalizeDept(item.department) === normalizeDept(activeTab);
      }
      
      // Status filter
      const matchesStatus = status === 'all' || item.status === status;
      
      // Date range filter
      let matchesDate = true;
      if (startDate) {
        matchesDate = matchesDate && item.receivedAt >= startDate;
      }
      if (endDate) {
        matchesDate = matchesDate && item.receivedAt <= `${endDate}T23:59:59.999Z`;
      }

      // Priority filter
      const matchesPriority = priorityFilter === 'all' || item.priority === priorityFilter;

      // Confidentiality filter
      const matchesConfidentiality = confidentialityFilter === 'all' || item.confidentiality === confidentialityFilter;

      // Text query search
      const matchesQuery = `${item.number} ${item.sender} ${item.subject}`.toLowerCase().includes(query.toLowerCase());

      return matchesTab && matchesStatus && matchesDate && matchesPriority && matchesConfidentiality && matchesQuery;
    });
  }, [result.data, activeTab, query, status, startDate, endDate, priorityFilter, confidentialityFilter]);

  const isHr = department.isHrWorkspace;

  const getCount = (tab: string) => {
    if (!result.data) return 0;
    if (tab === 'all') return result.data.length;
    if (tab === 'external') return result.data.filter(item => item.channel !== 'Внутренняя система').length;
    return result.data.filter(item => normalizeDept(item.department) === normalizeDept(tab)).length;
  };

  const hasActivePeriod = startDate || endDate;
  const hasActiveAdvanced = priorityFilter !== 'all' || confidentialityFilter !== 'all';

  return <>
    <PageHeader eyebrow={isHr ? 'HR · Сообщения' : 'Секретариат · Реестр'} title={isHr ? 'Входящие сообщения' : 'Входящая корреспонденция'} actions={<><button className="secondary-button"><Download size={16} /> Экспорт</button>{!isHr && <Link className="primary-button" to="/correspondence/incoming/new"><Plus size={16} /> Зарегистрировать письмо</Link>}</>} />
    
    <div className="message-tabs" role="tablist" aria-label="Категории сообщений">
      <button className={activeTab === 'external' ? 'active' : ''} onClick={() => setActiveTab('external')}>Внешние <b>{getCount('external')}</b></button>
      {departmentsList.map((dept) => (
        <button key={dept.name} className={activeTab === dept.name ? 'active' : ''} onClick={() => setActiveTab(dept.name)}>
          {dept.label} {getCount(dept.name) > 0 && <b>{getCount(dept.name)}</b>}
        </button>
      ))}
    </div>

    <div className="register-toolbar">
      <label className="field-search">
        <Search size={16} />
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Номер, отправитель или тема" />
      </label>
      
      <select value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="all">Все статусы</option>
        <option value="resolution">На резолюции</option>
        <option value="execution">В работе</option>
        <option value="approval">На согласовании</option>
        <option value="signature">На подписи</option>
        <option value="dispatch">К отправке</option>
      </select>

      <button className={`toolbar-button ${hasActivePeriod ? 'active' : ''}`} onClick={() => setIsFiltersDrawerOpen(true)}>
        <CalendarDays size={16} /> Период {hasActivePeriod && '●'}
      </button>

      <button className={`toolbar-button icon-only ${hasActiveAdvanced ? 'active' : ''}`} onClick={() => setIsFiltersDrawerOpen(true)}>
        <SlidersHorizontal size={16} />
      </button>

      <span className="view-toggle">
        <button className={viewMode === 'list' ? 'active' : ''} onClick={() => setViewMode('list')} aria-label="Списком">
          <List size={16} />
        </button>
        <button className={viewMode === 'grid' ? 'active' : ''} onClick={() => setViewMode('grid')} aria-label="Сеткой">
          <LayoutGrid size={16} />
        </button>
      </span>
    </div>

    {/* Right Sliding Filters Drawer */}
    {isFiltersDrawerOpen && (
      <div className="drawer-overlay" onClick={() => setIsFiltersDrawerOpen(false)}>
        <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
          <header className="drawer-header">
            <h2>Фильтры и период</h2>
            <button className="drawer-close" onClick={() => setIsFiltersDrawerOpen(false)} aria-label="Закрыть">×</button>
          </header>
          
          <div className="drawer-content">
            <section className="drawer-section">
              <h3>Период получения</h3>
              <div className="drawer-field-group">
                <label>
                  <span>Дата от</span>
                  <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
                </label>
                <label>
                  <span>Дата до</span>
                  <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
                </label>
              </div>
            </section>
            
            <section className="drawer-section">
              <h3>Параметры письма</h3>
              
              <label className="drawer-field">
                <span>Приоритет</span>
                <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)}>
                  <option value="all">Все приоритеты</option>
                  <option value="normal">Обычный</option>
                  <option value="high">Высокий</option>
                  <option value="urgent">Срочный</option>
                </select>
              </label>

              <label className="drawer-field">
                <span>Конфиденциальность</span>
                <select value={confidentialityFilter} onChange={(e) => setConfidentialityFilter(e.target.value)}>
                  <option value="all">Все уровни</option>
                  <option value="public">Открытый</option>
                  <option value="internal">ДСП</option>
                  <option value="restricted">Ограниченный доступ</option>
                </select>
              </label>
            </section>
          </div>

          <footer className="drawer-footer">
            <button className="secondary-button" onClick={() => {
              setStartDate('');
              setEndDate('');
              setPriorityFilter('all');
              setConfidentialityFilter('all');
            }}>
              Сбросить
            </button>
            <button className="primary-button" onClick={() => setIsFiltersDrawerOpen(false)}>
              Применить
            </button>
          </footer>
        </div>
      </div>
    )}

    {result.isLoading ? (
      <QueryState />
    ) : result.error ? (
      <QueryState error={result.error} retry={() => result.refetch()} />
    ) : filtered.length === 0 ? (
      <EmptyState title="Ничего не найдено" text="Измените запрос или сбросьте фильтры реестра." />
    ) : viewMode === 'grid' ? (
      <div className="correspondence-grid">
        {filtered.map((item) => (
          <article className="correspondence-card" key={item.id} onClick={() => location.assign(`/correspondence/incoming/${item.id}`)}>
            <header className="card-header">
              <Link to={`/correspondence/incoming/${item.id}`} className="card-number" onClick={(e) => e.stopPropagation()}>
                <strong>{item.number}</strong>
              </Link>
              <span className={`status-pill status-${item.status}`}>
                <i />{statusLabels[item.status]}
              </span>
            </header>
            <div className="card-body">
              <span className="card-date">{formatDate(item.receivedAt, locale, 'dd MMM yyyy, HH:mm')}</span>
              <h3 className="card-sender">{item.sender}</h3>
              <p className="card-subject">{item.subject}</p>
            </div>
            <footer className="card-footer">
              <div className="card-meta">
                <span>{item.department}</span>
                <small>{item.executor}</small>
              </div>
              <span className={`sla-chip ${item.priority === 'urgent' ? 'risk' : ''}`}>
                {item.priority === 'urgent' ? '1д 4ч' : '6д'}
              </span>
            </footer>
          </article>
        ))}
      </div>
    ) : (
      <div className="data-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Рег. номер</th>
              <th>Получено</th>
              <th>Отправитель / тема</th>
              <th>Подразделение</th>
              <th>Статус</th>
              <th>Срок</th>
              <th>SLA</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((item) => (
              <tr key={item.id} onClick={() => location.assign(`/correspondence/incoming/${item.id}`)}>
                <td>
                  <Link to={`/correspondence/incoming/${item.id}`} onClick={(e) => e.stopPropagation()}>
                    <strong>{item.number}</strong>
                    <small>{item.senderNumber}</small>
                  </Link>
                </td>
                <td>
                  {formatDate(item.receivedAt, locale, 'dd MMM')}
                  <small>{formatDate(item.receivedAt, locale, 'HH:mm')}</small>
                </td>
                <td className="subject-cell">
                  <strong>{item.sender}</strong>
                  <span>{item.subject}</span>
                </td>
                <td>
                  {item.department}
                  <small>{item.executor}</small>
                </td>
                <td>
                  <span className={`status-pill status-${item.status}`}><i />{statusLabels[item.status]}</span>
                  <small>{item.workflowStep}</small>
                </td>
                <td className={item.priority === 'urgent' ? 'text-coral' : ''}>
                  {formatDate(item.dueDate, locale, 'dd MMM yyyy')}
                </td>
                <td>
                  <span className={`sla-chip ${item.priority === 'urgent' ? 'risk' : ''}`}>
                    {item.priority === 'urgent' ? '1д 4ч' : '6д'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </>;
}
