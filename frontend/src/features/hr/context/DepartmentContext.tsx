import { createContext, useContext, useMemo, type PropsWithChildren } from 'react';
import { useLocation } from 'react-router-dom';
import { getPermissions } from '../../../shared/permissions';
import { getPersonaProfile, type DepartmentCode } from '../../../shared/personas';
import { useDeveloperStore } from '../../../shared/store';
import type { PersonaId } from '../../../shared/types';
import { UNIFIED_HR_WORKSPACE } from '../../../shared/unifiedHrWorkspace';

type DepartmentContextValue = { departmentId: string; departmentCode: DepartmentCode; departmentName: string; pageTitle: string; role: PersonaId; permissions: string[]; isHrWorkspace: boolean };
const DepartmentContext = createContext<DepartmentContextValue>({ departmentId: 'department-secretariat', departmentCode: 'SECRETARIAT', departmentName: 'Секретариат', pageTitle: 'Главная', role: 'secretary', permissions: [], isHrWorkspace: false });

const hrPages: Array<[RegExp, string]> = [
  [/\/employees\/[^/]+$/, 'Профиль сотрудника'], [/\/employees$/, 'Сотрудники'],
  [/\/hiring\/add-employee$/, 'Регистрация сотрудника'], [/\/leave$/, 'Система отпусков'], [/\/calendar$/, 'Календарь'],
  [/\/sick-leave$/, 'Система больничных'], [/\/business-trips$/, 'Командировки'],
  [/\/absence-calendar$/, 'Календарь отсутствий'], [/\/onboarding$/, 'Адаптация'],
  [/\/probation$/, 'Испытательный срок'], [/\/terminations$/, 'Прекращение отношений'],
  [/\/offboarding$/, 'Оффбординг'], [/\/messages$/, 'Входящие сообщения'],
  [/\/documents$/, 'Документы'], [/\/approvals$/, 'Согласования'], [/\/analytics$/, 'Аналитика'],
  [/\/systems$/, 'Кадровые системы'], [/\/hierarchy$/, 'Иерархия ролей'], [/\/hiring$/, 'Регламент найма'],
  [/\/(hr|departments\/hr)\/?$/, 'Главная']
];

export function DepartmentProvider({ children }: PropsWithChildren) {
  const { pathname, search } = useLocation();
  const persona = useDeveloperStore((state) => state.persona);
  const value = useMemo<DepartmentContextValue>(() => {
    const profile = getPersonaProfile(persona);
    const isHrRoute = pathname === '/hr' || pathname.startsWith('/hr/') || pathname === '/departments/hr' || pathname.startsWith('/departments/hr/');
    const isHrWorkspace = UNIFIED_HR_WORKSPACE || profile.departmentCode === 'HR';
    const isAddEmployee = pathname.endsWith('/employees') && new URLSearchParams(search).get('add') === 'true';
    const pageTitle = isAddEmployee
      ? 'Регистрация сотрудника'
      : isHrRoute
      ? hrPages.find(([pattern]) => pattern.test(pathname))?.[1] ?? 'Главная'
      : pathname.includes('/hiring/inbox') ? 'Входящие согласования'
      : pathname.includes('/business-trips') ? 'Командировки'
      : pathname.includes('/hiring/received') ? 'Документы новых сотрудников'
      : pathname.includes('/hiring/') ? 'Заявка на найм'
      : pathname.includes('incoming') ? (isHrWorkspace ? 'Входящие сообщения' : 'Входящая корреспонденция')
      : pathname.includes('tasks') ? 'Задачи'
      : pathname.includes('processes') ? 'Процессы'
      : pathname.includes('organization') ? 'Организация'
      : 'Главная';
    return {
      role: persona,
      permissions: getPermissions(persona) as string[],
      departmentId: UNIFIED_HR_WORKSPACE ? 'department-hr' : profile.departmentId,
      departmentCode: UNIFIED_HR_WORKSPACE || isHrRoute ? 'HR' : profile.departmentCode,
      departmentName: UNIFIED_HR_WORKSPACE || isHrRoute ? 'Департамент документооборота и управления персоналом' : profile.departmentName,
      pageTitle,
      isHrWorkspace
    };
  }, [pathname, persona, search]);
  return <DepartmentContext.Provider value={value}>{children}</DepartmentContext.Provider>;
}

export const useDepartmentContext = () => useContext(DepartmentContext);
