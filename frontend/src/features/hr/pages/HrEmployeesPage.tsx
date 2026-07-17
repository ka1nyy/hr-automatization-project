import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Building, CheckCircle2, ChevronDown, Search, UserCheck, UserPlus } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { EmptyState, PageHeader, QueryState } from '../../../shared/components';
import { usePermission } from '../../../shared/permissions';
import { hrRepository } from '../api';
import { EmployeeStatus } from '../components/HrStatus';
import HrAddEmployeePage from './HrAddEmployeePage';
import type { HrEmployeeStatus } from '../model/types';

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

export default function HrEmployeesPage() {
  const canRead = usePermission('hr.employees.read');
  const [searchParams, setSearchParams] = useSearchParams();
  const isAdding = searchParams.get('add') === 'true';
  const queryParam = searchParams.get('query') || '';
  const [query, setQuery] = useState(queryParam);
  const [department, setDepartment] = useState('all');
  const [statusFilter, setStatusFilter] = useState<'all' | HrEmployeeStatus>('all');
  
  const result = useQuery({ queryKey: ['hr', 'employees'], queryFn: () => hrRepository.listEmployees(), enabled: canRead });
  const collectionFunctions = useQuery({
    queryKey: ['employee-functions', 'collection'],
    queryFn: () => hrRepository.listCollectionFunctions(),
    enabled: canRead
  });
  const canHire = (collectionFunctions.data ?? []).some((item) => item.key === 'employee.hire');
  
  const deptFilteredEmployees = useMemo(() => {
    return (result.data ?? []).filter((employee) => {
      return department === 'all' || employee.department === department;
    });
  }, [result.data, department]);

  const counts = useMemo(() => {
    const list = deptFilteredEmployees;
    return {
      active: list.filter(e => e.status === 'active').length,
      on_leave: list.filter(e => e.status === 'on_leave').length,
      sick_leave: list.filter(e => e.status === 'sick_leave').length,
      probation: list.filter(e => e.status === 'probation').length,
    };
  }, [deptFilteredEmployees]);

  const filtered = useMemo(() => {
    return deptFilteredEmployees.filter((employee) => {
      const matchesStatus = statusFilter === 'all' || employee.status === statusFilter;
      const matchesQuery = `${employee.fullName} ${employee.position} ${employee.employeeNumber}`.toLowerCase().includes(query.toLowerCase());
      return matchesStatus && matchesQuery;
    });
  }, [deptFilteredEmployees, statusFilter, query]);

  const statusFilters = [
    { status: 'active', label: 'Активны', count: counts.active },
    { status: 'on_leave', label: 'В отпуске', count: counts.on_leave },
    { status: 'sick_leave', label: 'Больничный', count: counts.sick_leave },
    { status: 'probation', label: 'Испытательный срок', count: counts.probation },
  ] as const;

  const [isDeptOpen, setIsDeptOpen] = useState(false);

  const selectedDeptLabel = useMemo(() => {
    if (department === 'all') return 'Все подразделения';
    return departmentsList.find(d => d.name === department)?.label ?? department;
  }, [department]);

  const [isStatusOpen, setIsStatusOpen] = useState(false);

  const selectedStatusLabel = statusFilter === 'all'
    ? 'Все статусы'
    : statusFilters.find((item) => item.status === statusFilter)?.label ?? statusFilter;

  if (!canRead) return <div className="hr-access-denied"><span>HR</span><h1>Доступ ограничен</h1><p>Каталог сотрудников доступен только HR-ролям. Переключите developer persona на HR Specialist для проверки этой стороны.</p><Link className="secondary-button" to="/departments/hr">Вернуться в HR</Link></div>;

  if (isAdding) {
    return <HrAddEmployeePage onBack={() => setSearchParams((prev) => { prev.delete('add'); return prev; })} />;
  }

  return <>
    <PageHeader eyebrow="HR · Сотрудники" title="Сотрудники" actions={canHire ? <button type="button" className="primary-button" onClick={() => setSearchParams((prev) => { prev.set('add', 'true'); return prev; })}><UserPlus size={16} /> Добавить сотрудника</button> : undefined} />
    {searchParams.get('lifecycle') === 'terminated' && <div className="success-banner"><CheckCircle2 size={20} /><span><strong>Увольнение зарегистрировано</strong>Сотрудник исключён из активного состава, его назначения и будущие отсутствия завершены.</span></div>}
    <div className="register-toolbar hr-toolbar">
      <label className="field-search" style={{ flex: 1 }}>
        <Search size={16} />
        <input
          value={query}
          onChange={(event) => {
            const val = event.target.value;
            setQuery(val);
            setSearchParams(prev => {
              if (val) prev.set('query', val);
              else prev.delete('query');
              return prev;
            });
          }}
          placeholder="ФИО, должность или табельный номер"
        />
      </label>

      {/* Custom Department Dropdown Selector */}
      <div className="custom-select-container">
        <button 
          type="button" 
          className={`custom-select-btn ${department !== 'all' ? 'active' : ''}`}
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
                className={`select-option ${department === 'all' ? 'selected' : ''}`}
                onClick={() => {
                  setDepartment('all');
                  setIsDeptOpen(false);
                }}
              >
                <span>Все подразделения</span>
                <span className="option-count">{result.data?.length ?? 0}</span>
              </button>
              {departmentsList.map((dept) => {
                const count = (result.data ?? []).filter(emp => emp.department === dept.name).length;
                const isSelected = department === dept.name;
                return (
                  <button 
                    key={dept.name}
                    type="button" 
                    className={`select-option ${isSelected ? 'selected' : ''}`}
                    onClick={() => {
                      setDepartment(dept.name);
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
          className={`custom-select-btn ${statusFilter !== 'all' ? 'active' : ''}`}
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
                className={`select-option ${statusFilter === 'all' ? 'selected' : ''}`}
                onClick={() => {
                  setStatusFilter('all');
                  setIsStatusOpen(false);
                }}
              >
                <span>Все статусы</span>
                <span className="option-count">{deptFilteredEmployees.length}</span>
              </button>
              {statusFilters.map((sf) => {
                const isSelected = statusFilter === sf.status;
                return (
                  <button 
                    key={sf.status}
                    type="button" 
                    className={`select-option ${isSelected ? 'selected' : ''}`}
                    onClick={() => {
                      setStatusFilter(sf.status);
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
    </div>

    {result.isLoading ? (
      <QueryState />
    ) : result.error ? (
      <QueryState error={result.error} retry={() => result.refetch()} />
    ) : filtered.length === 0 ? (
      <EmptyState title="Сотрудники не найдены" text="Измените поиск или фильтр подразделения." />
    ) : (
      <div className="data-table-wrap">
        <table className="data-table hr-employee-table">
          <thead>
            <tr>
              <th>Сотрудник</th>
              <th>Должность</th>
              <th>Подразделение</th>
              <th>Руководитель</th>
              <th>Статус</th>
              <th>Личное дело</th>
              <th>Остаток</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((employee) => (
              <tr key={employee.id}>
                <td>
                  <Link className="hr-employee-cell" to={`/departments/hr/employees/${employee.id}`}>
                    <span className="avatar">{employee.initials}</span>
                    <span>
                      <strong>{employee.fullName}</strong>
                      <small>{employee.employeeNumber} · {employee.workEmail}</small>
                    </span>
                  </Link>
                </td>
                <td>{employee.position}<small>{employee.employmentType}</small></td>
                <td>{employee.department}<small>{employee.location}</small></td>
                <td>{employee.manager ?? 'Не назначен'}</td>
                <td><EmployeeStatus status={employee.status} /></td>
                <td>
                  <span className="hr-completeness">
                    <i><b style={{ width: `${employee.personnelFileCompleteness}%` }} /></i>
                    {employee.personnelFileCompleteness}%
                  </span>
                </td>
                <td><strong>{employee.leaveBalance}</strong> дней</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </>;
}
