import { createContext, useContext, useMemo, type PropsWithChildren } from 'react';
import { useLocation } from 'react-router-dom';

type DepartmentContextValue = { departmentCode: 'HR' | null; pageTitle: string };
const DepartmentContext = createContext<DepartmentContextValue>({ departmentCode: null, pageTitle: 'Главная' });

const hrPages: Array<[RegExp, string]> = [
  [/\/employees\/[^/]+$/, 'Профиль сотрудника'], [/\/employees$/, 'Сотрудники'],
  [/\/hiring\/add-employee$/, 'Добавить сотрудника'], [/\/leave$/, 'Отпуска'],
  [/\/sick-leave$/, 'Больничные'], [/\/business-trips$/, 'Командировки'],
  [/\/absence-calendar$/, 'Календарь отсутствий'], [/\/onboarding$/, 'Адаптация'],
  [/\/probation$/, 'Испытательный срок'], [/\/terminations$/, 'Увольнения'],
  [/\/offboarding$/, 'Оффбординг'], [/\/messages$/, 'Входящие сообщения'],
  [/\/analytics$/, 'Аналитика'], [/\/(hr|departments\/hr)\/?$/, 'Главная']
];

export function DepartmentProvider({ children }: PropsWithChildren) {
  const { pathname } = useLocation();
  const value = useMemo<DepartmentContextValue>(() => {
    const isHr = pathname === '/hr' || pathname.startsWith('/hr/') || pathname === '/departments/hr' || pathname.startsWith('/departments/hr/');
    if (isHr) return { departmentCode: 'HR', pageTitle: hrPages.find(([pattern]) => pattern.test(pathname))?.[1] ?? 'Рабочее пространство' };
    if (pathname.includes('incoming')) return { departmentCode: null, pageTitle: 'Входящая корреспонденция' };
    if (pathname.includes('tasks')) return { departmentCode: null, pageTitle: 'Задачи' };
    if (pathname.includes('processes')) return { departmentCode: null, pageTitle: 'Процессы' };
    if (pathname.includes('organization')) return { departmentCode: null, pageTitle: 'Организация' };
    return { departmentCode: null, pageTitle: 'Главная' };
  }, [pathname]);
  return <DepartmentContext.Provider value={value}>{children}</DepartmentContext.Provider>;
}

export const useDepartmentContext = () => useContext(DepartmentContext);
