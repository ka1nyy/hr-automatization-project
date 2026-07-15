import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, UserPlus } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { EmptyState, PageHeader, QueryState } from '../../../shared/components';
import { usePermission } from '../../../shared/permissions';
import { hrRepository } from '../api';
import { EmployeeStatus } from '../components/HrStatus';

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
  const queryParam = searchParams.get('query') || '';
  const [query, setQuery] = useState(queryParam);
  const [department, setDepartment] = useState('all');
  const result = useQuery({ queryKey: ['hr', 'employees'], queryFn: () => hrRepository.listEmployees(), enabled: canRead });
  
  const departments = useMemo(() => {
    return [...new Set((result.data ?? []).map((item) => item.department))];
  }, [result.data]);

  const filtered = useMemo(() => {
    return (result.data ?? []).filter((employee) => {
      const matchesDept = department === 'all' || employee.department === department;
      const matchesQuery = `${employee.fullName} ${employee.position} ${employee.employeeNumber}`.toLowerCase().includes(query.toLowerCase());
      return matchesDept && matchesQuery;
    });
  }, [result.data, department, query]);

  if (!canRead) return <div className="hr-access-denied"><span>HR</span><h1>Доступ ограничен</h1><p>Каталог сотрудников доступен только HR-ролям. Переключите developer persona на HR Specialist для проверки этой стороны.</p><Link className="secondary-button" to="/departments/hr">Вернуться в HR</Link></div>;

  return <>
    <PageHeader eyebrow="HR · Сотрудники" title="Сотрудники" actions={<Link className="primary-button" to="/hr/hiring/add-employee"><UserPlus size={16} /> Добавить сотрудника</Link>} />
    <div className="hr-directory-summary">
      <span><strong>{result.data?.length ?? 0}</strong> сотрудников</span>
      <span><strong>{departments.length}</strong> подразделений</span>
      <span><strong>{(result.data ?? []).filter((employee) => employee.status === 'probation').length}</strong> на испытательном сроке</span>
      <span><strong>{(result.data ?? []).filter((employee) => employee.status === 'on_leave' || employee.status === 'sick_leave').length}</strong> отсутствуют</span>
    </div>

    <div className="message-tabs" role="tablist" aria-label="Фильтр по департаментам">
      {departmentsList.map((dept) => {
        const isActive = department === dept.name;
        const count = (result.data ?? []).filter(emp => emp.department === dept.name).length;
        return (
          <button
            key={dept.name}
            className={isActive ? 'active' : ''}
            onClick={() => setDepartment(isActive ? 'all' : dept.name)}
          >
            {dept.label} {count > 0 && <b>{count}</b>}
          </button>
        );
      })}
    </div>

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
