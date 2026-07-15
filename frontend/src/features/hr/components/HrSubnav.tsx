import { CalendarDays, LayoutDashboard, UserPlus, UsersRound } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { usePermission } from '../../../shared/permissions';

export function HrSubnav() {
  const canReadEmployees = usePermission('hr.employees.read');
  return <nav className="hr-subnav" aria-label="Навигация HR пространства">
    <NavLink to="/hr" end><LayoutDashboard size={16} />Главная</NavLink>
    {canReadEmployees && <NavLink to="/hr/employees"><UsersRound size={16} />Сотрудники</NavLink>}
    <NavLink to="/hr/hiring/add-employee"><UserPlus size={16} />Добавить сотрудника</NavLink>
    <NavLink to="/hr/leave"><CalendarDays size={16} />Отпуска</NavLink>
  </nav>;
}
