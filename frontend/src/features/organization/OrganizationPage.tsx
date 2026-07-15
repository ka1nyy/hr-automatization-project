import { useQuery } from '@tanstack/react-query';
import { Building2, Network, Search, ShieldCheck, UsersRound } from 'lucide-react';
import { repositories } from '../../repositories';
import { PageHeader, QueryState, Section } from '../../shared/components';
import { useDepartmentContext } from '../hr/context/DepartmentContext';

export default function OrganizationPage() {
  const department = useDepartmentContext();
  const result = useQuery({ queryKey: ['employees'], queryFn: () => repositories.organization.listEmployees() });
  return <>
    <PageHeader eyebrow={`${department.departmentCode} · Organization Service`} title="Организация и назначения" actions={<button className="secondary-button"><Network size={16} /> Оргструктура</button>} />
    <div className="organization-summary"><article><Building2 size={20} /><span><strong>13</strong><small>подразделений</small></span></article><article><UsersRound size={20} /><span><strong>180</strong><small>сотрудников</small></span></article><article><ShieldCheck size={20} /><span><strong>30</strong><small>процессных ролей</small></span></article></div>
    <Section title="Корпоративный справочник" meta="Детерминированный mock-набор"><div className="directory-toolbar"><label className="field-search"><Search size={16} /><input placeholder="ФИО, должность или подразделение" /></label><select><option>Все подразделения</option><option>Департамент документооборота и управления персоналом</option><option>Департамент инвестиций</option><option>Департамент кредитования</option><option>Департамент активов</option><option>Департамент строительства</option><option>Департамент стабильности фонда</option><option>Департамент экономического планирования</option><option>Юридический департамент</option><option>Бухгалтерия</option></select></div>{result.isLoading ? <QueryState /> : result.error ? <QueryState error={result.error} retry={() => result.refetch()} /> : <div className="employee-grid">{result.data!.map((employee) => <article key={employee.id}><span className="avatar">{employee.initials}</span><div><h2>{employee.name}</h2><p>{employee.role}</p><small>{employee.department}</small></div><span className={`employee-state ${employee.status}`}>{employee.status === 'active' ? 'Активен' : employee.status === 'acting' ? 'И.о.' : 'Делегировано'}</span>{!department.isHrWorkspace && <footer>{employee.candidateGroups.map((group) => <code key={group}>{group}</code>)}</footer>}</article>)}</div>}</Section>
  </>;
}
