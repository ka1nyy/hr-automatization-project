import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, LayoutGrid, List, Search, SlidersHorizontal, UserPlus } from 'lucide-react';
import { Link } from 'react-router-dom';
import { EmptyState, PageHeader, QueryState } from '../../../shared/components';
import { usePermission } from '../../../shared/permissions';
import { hrRepository } from '../api';
import { EmployeeStatus } from '../components/HrStatus';

export default function HrEmployeesPage() {
  const canRead = usePermission('hr.employees.read');
  const [query, setQuery] = useState('');
  const [department, setDepartment] = useState('all');
  const result = useQuery({ queryKey: ['hr', 'employees'], queryFn: () => hrRepository.listEmployees(), enabled: canRead });
  const departments = [...new Set((result.data ?? []).map((item) => item.department))];
  const filtered = useMemo(() => (result.data ?? []).filter((employee) => (department === 'all' || employee.department === department) && `${employee.fullName} ${employee.position} ${employee.employeeNumber}`.toLowerCase().includes(query.toLowerCase())), [result.data, department, query]);

  if (!canRead) return <div className="hr-access-denied"><span>HR</span><h1>Доступ ограничен</h1><p>Каталог сотрудников доступен только HR-ролям. Переключите developer persona на HR Specialist для проверки этой стороны.</p><Link className="secondary-button" to="/departments/hr">Вернуться в HR</Link></div>;
  return <>
    <PageHeader eyebrow="HR · Сотрудники" title="Сотрудники" description="Штат, статусы занятости и полнота кадровых данных." actions={<><button className="secondary-button"><Download size={16} /> Экспорт</button><Link className="primary-button" to="/hr/hiring/add-employee"><UserPlus size={16} /> Добавить сотрудника</Link></>} />
    <div className="hr-directory-summary"><span><strong>180</strong> сотрудников</span><span><strong>8</strong> подразделений</span><span><strong>12</strong> на испытательном сроке</span><span><strong>15</strong> отсутствуют</span></div>
    <div className="register-toolbar hr-toolbar"><label className="field-search"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="ФИО, должность или табельный номер" /></label><select value={department} onChange={(event) => setDepartment(event.target.value)}><option value="all">Все подразделения</option>{departments.map((item) => <option key={item}>{item}</option>)}</select><button className="toolbar-button"><SlidersHorizontal size={16} /> Колонки</button><span className="view-toggle"><button className="active"><List size={16} /></button><button><LayoutGrid size={16} /></button></span></div>
    {result.isLoading ? <QueryState /> : result.error ? <QueryState error={result.error} retry={() => result.refetch()} /> : filtered.length === 0 ? <EmptyState title="Сотрудники не найдены" text="Измените поиск или фильтр подразделения." /> : <div className="data-table-wrap"><table className="data-table hr-employee-table"><thead><tr><th>Сотрудник</th><th>Должность</th><th>Подразделение</th><th>Руководитель</th><th>Статус</th><th>Личное дело</th><th>Остаток</th></tr></thead><tbody>{filtered.map((employee) => <tr key={employee.id}><td><Link className="hr-employee-cell" to={`/departments/hr/employees/${employee.id}`}><span className="avatar">{employee.initials}</span><span><strong>{employee.fullName}</strong><small>{employee.employeeNumber} · {employee.workEmail}</small></span></Link></td><td>{employee.position}<small>{employee.employmentType}</small></td><td>{employee.department}<small>{employee.location}</small></td><td>{employee.manager ?? 'Не назначен'}</td><td><EmployeeStatus status={employee.status} /></td><td><span className="hr-completeness"><i><b style={{ width: `${employee.personnelFileCompleteness}%` }} /></i>{employee.personnelFileCompleteness}%</span></td><td><strong>{employee.leaveBalance}</strong> дней</td></tr>)}</tbody></table></div>}
  </>;
}
