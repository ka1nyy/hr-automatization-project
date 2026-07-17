import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Building, CalendarDays, ChevronDown, Plus, Search, UserCheck } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
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
  const navigate = useNavigate();
  
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [selectedDept, setSelectedDept] = useState('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const [isDeptOpen, setIsDeptOpen] = useState(false);
  const [isStatusOpen, setIsStatusOpen] = useState(false);

  const result = useQuery({ queryKey: ['incoming'], queryFn: () => repositories.correspondence.listIncoming() });

  const deptFilteredIncoming = useMemo(() => {
    return (result.data ?? []).filter((item) => {
      return selectedDept === 'all' || normalizeDept(item.department) === normalizeDept(selectedDept);
    });
  }, [result.data, selectedDept]);

  const statusCounts = useMemo(() => {
    const list = deptFilteredIncoming;
    return {
      resolution: list.filter(item => item.status === 'resolution').length,
      execution: list.filter(item => item.status === 'execution').length,
      approval: list.filter(item => item.status === 'approval').length,
      signature: list.filter(item => item.status === 'signature').length,
      dispatch: list.filter(item => item.status === 'dispatch').length,
    };
  }, [deptFilteredIncoming]);

  const filtered = useMemo(() => {
    return deptFilteredIncoming.filter((item) => {
      const matchesStatus = status === 'all' || item.status === status;
      
      let matchesDate = true;
      if (startDate) {
        matchesDate = matchesDate && item.receivedAt >= startDate;
      }
      if (endDate) {
        matchesDate = matchesDate && item.receivedAt <= `${endDate}T23:59:59.999Z`;
      }

      const matchesQuery = `${item.number} ${item.sender} ${item.subject}`.toLowerCase().includes(query.toLowerCase());

      return matchesStatus && matchesDate && matchesQuery;
    });
  }, [deptFilteredIncoming, status, startDate, endDate, query]);

  const isHr = department.isHrWorkspace;

  const selectedDeptLabel = useMemo(() => {
    if (selectedDept === 'all') return 'Все подразделения';
    return departmentsList.find(d => d.name === selectedDept)?.label ?? selectedDept;
  }, [selectedDept]);

  const statusFilters = [
    { status: 'resolution', label: 'На резолюции', count: statusCounts.resolution },
    { status: 'execution', label: 'В работе', count: statusCounts.execution },
    { status: 'approval', label: 'На согласовании', count: statusCounts.approval },
    { status: 'signature', label: 'На подписи', count: statusCounts.signature },
    { status: 'dispatch', label: 'К отправке', count: statusCounts.dispatch },
  ] as const;

  const selectedStatusLabel = status === 'all'
    ? 'Все статусы'
    : statusFilters.find((item) => item.status === status)?.label ?? status;

  return <>
    <PageHeader eyebrow={isHr ? 'HR · Входящие сообщения' : 'Секретариат · Реестр'} title={isHr ? 'Входящие сообщения' : 'Входящая корреспонденция'} actions={!isHr ? <Link className="primary-button" to="/correspondence/incoming/new"><Plus size={16} /> Зарегистрировать письмо</Link> : undefined} />
    
    <div className="register-toolbar">
      <label className="field-search" style={{ flex: 1 }}>
        <Search size={16} />
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Номер, отправитель или тема" />
      </label>
      
      {/* Custom Department Dropdown Selector */}
      <div className="custom-select-container">
        <button 
          type="button" 
          className={`custom-select-btn ${selectedDept !== 'all' ? 'active' : ''}`}
          onClick={() => setIsDeptOpen(!isDeptOpen)}
        >
          <Building size={14} className="select-icon" />
          <span>{selectedDeptLabel}</span>
          <ChevronDown size={14} className={`arrow-icon ${isDeptOpen ? 'open' : ''}`} />
        </button>
        
        {isDeptOpen && (
          <>
            <div className="custom-select-overlay" onClick={() => setIsDeptOpen(false)} />
            <div className="custom-select-dropdown">
              <button 
                type="button" 
                className={`select-option ${selectedDept === 'all' ? 'selected' : ''}`}
                onClick={() => {
                  setSelectedDept('all');
                  setIsDeptOpen(false);
                }}
              >
                <span>Все подразделения</span>
                <span className="option-count">{result.data?.length ?? 0}</span>
              </button>
              {departmentsList.map((dept) => {
                const count = (result.data ?? []).filter(item => normalizeDept(item.department) === normalizeDept(dept.name)).length;
                const isSelected = selectedDept === dept.name;
                return (
                  <button 
                    key={dept.name}
                    type="button" 
                    className={`select-option ${isSelected ? 'selected' : ''}`}
                    onClick={() => {
                      setSelectedDept(dept.name);
                      setIsDeptOpen(false);
                    }}
                  >
                    <span>{dept.label}</span>
                    <span className="option-count">{count}</span>
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* Custom Status Dropdown Selector */}
      <div className="custom-select-container">
        <button 
          type="button" 
          className={`custom-select-btn ${status !== 'all' ? 'active' : ''}`}
          onClick={() => setIsStatusOpen(!isStatusOpen)}
        >
          <UserCheck size={14} className="select-icon" />
          <span>{selectedStatusLabel}</span>
          <ChevronDown size={14} className={`arrow-icon ${isStatusOpen ? 'open' : ''}`} />
        </button>
        
        {isStatusOpen && (
          <>
            <div className="custom-select-overlay" onClick={() => setIsStatusOpen(false)} />
            <div className="custom-select-dropdown">
              <button 
                type="button" 
                className={`select-option ${status === 'all' ? 'selected' : ''}`}
                onClick={() => {
                  setStatus('all');
                  setIsStatusOpen(false);
                }}
              >
                <span>Все статусы</span>
                <span className="option-count">{deptFilteredIncoming.length}</span>
              </button>
              {statusFilters.map((sf) => {
                const isSelected = status === sf.status;
                return (
                  <button 
                    key={sf.status}
                    type="button" 
                    className={`select-option ${isSelected ? 'selected' : ''}`}
                    onClick={() => {
                      setStatus(sf.status);
                      setIsStatusOpen(false);
                    }}
                  >
                    <span>{sf.label}</span>
                    <span className="option-count">{sf.count}</span>
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* Date Range Group with Calendar icons */}
      <div className="date-range-group">
        <div className="date-field">
          <CalendarDays size={14} />
          <input 
            type="date" 
            value={startDate} 
            onChange={(e) => setStartDate(e.target.value)} 
            title="Дата начала"
          />
        </div>
        <span className="date-separator">—</span>
        <div className="date-field">
          <CalendarDays size={14} />
          <input 
            type="date" 
            value={endDate} 
            onChange={(e) => setEndDate(e.target.value)} 
            title="Дата конца"
          />
        </div>
      </div>
    </div>

    {result.isLoading ? (
      <QueryState />
    ) : result.error ? (
      <QueryState error={result.error} retry={() => result.refetch()} />
    ) : filtered.length === 0 ? (
      <EmptyState title="Ничего не найдено" text="Измените запрос или сбросьте фильтры реестра." />
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
              <tr key={item.id} onClick={() => navigate(`/correspondence/incoming/${item.id}`)}>
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
