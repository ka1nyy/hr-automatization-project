import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Building2, Search, ShieldCheck, UsersRound } from 'lucide-react';
import { repositories } from '../../repositories';
import { PageHeader, QueryState, Section } from '../../shared/components';
import { useDepartmentContext } from '../hr/context/DepartmentContext';

export default function OrganizationPage() {
  const department = useDepartmentContext();
  const [search, setSearch] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState('all');
  const result = useQuery({ queryKey: ['employees'], queryFn: () => repositories.organization.listEmployees() });
  const departments = [...new Set((result.data ?? []).map((employee) => employee.department))];
  const employees = useMemo(() => (result.data ?? []).filter((employee) => {
    const matchesDepartment = departmentFilter === 'all' || employee.department === departmentFilter;
    return matchesDepartment && `${employee.name} ${employee.role} ${employee.department}`.toLowerCase().includes(search.toLowerCase());
  }), [result.data, departmentFilter, search]);
  return <>
    <PageHeader eyebrow={`${department.departmentCode} · Organization Service`} title="Организация и назначения" />
    <div className="organization-summary"><article><Building2 size={20} /><span><strong>{departments.length}</strong><small>подразделений</small></span></article><article><UsersRound size={20} /><span><strong>{result.data?.length ?? 0}</strong><small>сотрудников</small></span></article><article><ShieldCheck size={20} /><span><strong>{new Set((result.data ?? []).flatMap((employee) => employee.candidateGroups)).size}</strong><small>процессных ролей</small></span></article></div>
    <Section title="Корпоративный справочник" meta="Данные Organization Service"><div className="directory-toolbar"><label className="field-search"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="ФИО, должность или подразделение" /></label><select value={departmentFilter} onChange={(event) => setDepartmentFilter(event.target.value)}><option value="all">Все подразделения</option>{departments.map((item) => <option key={item}>{item}</option>)}</select></div>{result.isLoading ? <QueryState /> : result.error ? <QueryState error={result.error} retry={() => result.refetch()} /> : <div className="employee-grid">{employees.map((employee) => <article key={employee.id}><span className="avatar">{employee.initials}</span><div><h2>{employee.name}</h2><p>{employee.role}</p><small>{employee.department}</small></div><span className={`employee-state ${employee.status}`}>{employee.status === 'active' ? 'Активен' : employee.status === 'acting' ? 'И.о.' : 'Делегировано'}</span>{!department.isHrWorkspace && <footer>{employee.candidateGroups.map((group) => <code key={group}>{group}</code>)}</footer>}</article>)}</div>}</Section>
  </>;
}
