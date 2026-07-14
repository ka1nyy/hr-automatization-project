import { CalendarDays, LayoutDashboard, UsersRound } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { usePermission } from '../../../shared/permissions';

export function HrSubnav() {
  const canReadEmployees = usePermission('hr.employees.read');
  return <nav className="hr-subnav" aria-label="Навигация HR пространства">
    <NavLink to="/departments/hr" end><LayoutDashboard size={16} />Обзор</NavLink>
    {canReadEmployees && <NavLink to="/departments/hr/employees"><UsersRound size={16} />Сотрудники</NavLink>}
    <NavLink to="/departments/hr/leave"><CalendarDays size={16} />Отпуска</NavLink>
  </nav>;
}
