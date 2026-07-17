import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, BriefcaseBusiness, CalendarDays, CheckCircle2, FileText, Mail, MapPin, Phone, ShieldCheck, UserRound } from 'lucide-react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { PageHeader, QueryState, Section } from '../../../shared/components';
import { formatDate } from '../../../shared/format';
import { usePermission } from '../../../shared/permissions';
import { useDeveloperStore } from '../../../shared/store';
import { hrRepository } from '../api';
import { EmployeeActions } from '../components/EmployeeActions';
import { EmployeeAbsencesSection } from '../components/EmployeeAbsencesSection';
import { TerminationSection } from '../components/TerminationSection';
import { EmployeeStatus } from '../components/HrStatus';

export default function HrEmployeeProfilePage() {
  const { employeeId = '' } = useParams();
  const [searchParams] = useSearchParams();
  const locale = useDeveloperStore((state) => state.locale);
  const canReadAll = usePermission('hr.employees.read');
  const canReadSensitive = usePermission('hr.sensitive.read');
  const currentEmployee = useQuery({
    queryKey: ['hr', 'employee', 'me'],
    queryFn: () => hrRepository.getCurrentEmployee(),
    enabled: !canReadAll
  });
  const isOwnProfile = currentEmployee.data?.id === employeeId;
  const allowed = canReadAll || isOwnProfile;
  const result = useQuery({ queryKey: ['hr', 'employee', employeeId], queryFn: () => hrRepository.getEmployee(employeeId), enabled: allowed });
  if (!canReadAll && currentEmployee.isLoading) return <QueryState />;
  if (!allowed) return <div className="hr-access-denied"><span>HR</span><h1>Профиль недоступен</h1><p>Сотрудник может просматривать только собственный профиль.</p><Link className="secondary-button" to="/departments/hr">Вернуться в HR</Link></div>;
  if (result.isLoading) return <QueryState />;
  if (result.error || !result.data) return <QueryState error={result.error ?? new Error('Сотрудник не найден')} retry={() => result.refetch()} />;
  const employee = result.data;
  return <>
    <PageHeader eyebrow={`Сотрудники · ${employee.employeeNumber}`} title={employee.fullName} description={`${employee.position} · ${employee.department}`} actions={<><EmployeeActions employeeId={employee.id} /><Link className="secondary-button" to={canReadAll ? '/departments/hr/employees' : '/departments/hr'}><ArrowLeft size={16} /> Назад</Link></>} />
    {searchParams.get('hired') === '1' && <div className="success-banner"><CheckCircle2 size={20} /><span><strong>Сотрудник зачислен в штат</strong>Карточка создана в backend и уже доступна в общем списке сотрудников.</span></div>}
    <div className="hr-profile-header">
      <span className="avatar hr-avatar-xl">{employee.initials}</span><div className="hr-profile-identity"><EmployeeStatus status={employee.status} /><strong>{employee.position}</strong><span>{employee.department}</span></div>
      <div className="hr-profile-contact"><span><Mail size={15} />{employee.workEmail}</span><span><Phone size={15} />{employee.phone}</span><span><MapPin size={15} />{employee.location}</span></div>
      <div className="hr-profile-score"><span>Личное дело</span><strong>{employee.personnelFileCompleteness}%</strong><i><b style={{ width: `${employee.personnelFileCompleteness}%` }} /></i></div>
    </div>
    <div className="hr-profile-grid">
      <div className="hr-profile-main">
        <Section title="Рабочая информация"><dl className="metadata-grid"><div><dt>Табельный номер</dt><dd>{employee.employeeNumber}</dd></div><div><dt>Дата выхода</dt><dd>{formatDate(employee.startDate, locale)}</dd></div><div><dt>Тип занятости</dt><dd>{employee.employmentType}</dd></div><div><dt>Локация</dt><dd>{employee.location}</dd></div><div><dt>Руководитель</dt><dd>{employee.manager ?? 'Не назначен'}</dd></div><div><dt>Окончание договора</dt><dd>{employee.contractEnd ? formatDate(employee.contractEnd, locale) : 'Бессрочный'}</dd></div><div><dt>Испытательный срок</dt><dd>{employee.probationEnd ? `до ${formatDate(employee.probationEnd, locale)}` : 'Завершён'}</dd></div></dl></Section>
        <EmployeeAbsencesSection employeeId={employee.id} />
        <TerminationSection employee={employee} />
        <Section title="Компетенции и развитие"><div className="hr-skill-list">{employee.skills.map((skill) => <span key={skill}>{skill}</span>)}</div><div className="hr-development-note"><BriefcaseBusiness size={18} /><span><strong>План развития на 2026 год</strong><small>2 цели в работе · следующая встреча 22 июля</small></span></div></Section>
        <Section title="Последняя активность"><div className="audit-list"><div><i /><span><strong>Профиль сотрудника обновлён</strong><small>HR Service · 12 июля</small><p>Проверены контактные данные и место работы.</p></span></div><div><i /><span><strong>Создана заявка на отпуск</strong><small>Leave Request v2 · 14 июля</small><p>Документ ожидает согласования руководителя.</p></span></div></div></Section>
      </div>
      <aside className="hr-profile-aside">
        <Section title="Отпуск"><div className="hr-leave-card"><CalendarDays size={21} /><strong>{employee.leaveBalance}<small>дней доступно</small></strong><Link to="/departments/hr/leave">Создать заявку</Link></div></Section>
        <Section title="Компенсация"><div className="hr-sensitive-field"><span>Текущий оклад</span>{canReadSensitive ? <strong>{new Intl.NumberFormat('ru-RU').format(employee.salary)} {employee.currency}</strong> : <strong className="restricted-value"><ShieldCheck size={15} /> Ограничено</strong>}<small>{canReadSensitive ? 'Ежемесячно · gross' : 'Требуется hr.sensitive.read'}</small></div></Section>
        <Section title="Документы"><div className="hr-document-shortcuts"><div><FileText size={16} />Трудовой договор <span>активен</span></div><div><FileText size={16} />Приказ о приёме <span>подписан</span></div><div><UserRound size={16} />Личная карточка <span>{employee.personnelFileCompleteness}%</span></div></div></Section>
      </aside>
    </div>
  </>;
}
