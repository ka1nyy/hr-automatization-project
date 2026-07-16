import { CalendarDays, HeartPulse, LayoutDashboard, UsersRound } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { usePermission } from '../../../shared/permissions';
import { useDeveloperStore } from '../../../shared/store';
import { t } from '../../../shared/i18n';

export function HrSubnav() {
  const canReadEmployees = usePermission('hr.employees.read');
  const locale = useDeveloperStore((state) => state.locale);
  return <nav className="hr-subnav" aria-label="Навигация HR пространства">
    <NavLink to="/hr" end><LayoutDashboard size={16} />{t(locale, 'home')}</NavLink>
    {canReadEmployees && <NavLink to="/hr/employees"><UsersRound size={16} />{t(locale, 'employees')}</NavLink>}
    <NavLink to="/hr/calendar"><CalendarDays size={16} />Календарь</NavLink>
    <NavLink to="/hr/leave"><CalendarDays size={16} />{t(locale, 'leave')}</NavLink>
    <NavLink to="/hr/sick-leave"><HeartPulse size={16} />Больничные</NavLink>
  </nav>;
}
