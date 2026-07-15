import type { PersonaId } from './types';

export type DepartmentCode = 'HR' | 'EXECUTIVE' | 'SECRETARIAT' | 'STRATEGY' | 'DIGITAL';

export type PersonaProfile = {
  id: PersonaId;
  name: string;
  role: string;
  departmentId: string;
  departmentCode: DepartmentCode;
  departmentName: string;
  email: string;
  homePath: string;
};

export const personaProfiles: Record<PersonaId, PersonaProfile> = {
  secretary: {
    id: 'secretary', name: 'Алия Омарова', role: 'Секретарь', departmentId: 'department-secretariat',
    departmentCode: 'SECRETARIAT', departmentName: 'Секретариат', email: 'a.omarova@ertis.kz', homePath: '/'
  },
  executive: {
    id: 'executive', name: 'Айдар Нурланов', role: 'Председатель Правления', departmentId: 'department-executive',
    departmentCode: 'EXECUTIVE', departmentName: 'Руководство', email: 'a.nurlanov@ertis.kz', homePath: '/'
  },
  employee: {
    id: 'employee', name: 'Мадина Садыкова', role: 'Главный эксперт', departmentId: 'department-strategy',
    departmentCode: 'STRATEGY', departmentName: 'Департамент экономического планирования', email: 'm.sadykova@ertis.kz', homePath: '/'
  },
  'hr-specialist': {
    id: 'hr-specialist', name: 'Зарина Ахметова', role: 'HR специалист', departmentId: 'department-hr',
    departmentCode: 'HR', departmentName: 'Департамент документооборота и управления персоналом', email: 'z.akhmetova@ertis.kz', homePath: '/'
  },
  'process-designer': {
    id: 'process-designer', name: 'Диана Абилова', role: 'Процессный архитектор', departmentId: 'department-digital',
    departmentCode: 'DIGITAL', departmentName: 'Цифровая трансформация', email: 'd.abilova@ertis.kz', homePath: '/'
  }
};

export const getPersonaProfile = (persona: PersonaId) => personaProfiles[persona];

