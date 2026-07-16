import type { PersonaId } from './types';

export type DepartmentCode = 'HR' | 'EXECUTIVE' | 'SECRETARIAT' | 'STRATEGY' | 'DIGITAL' | 'LEGAL' | 'ACCOUNTING' | 'IT' | 'COMMISSION';

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
  },
  'hr-initiator': { id: 'hr-initiator', name: 'Айгерим Садыкова', role: 'Сотрудник HR', departmentId: 'department-hr', departmentCode: 'HR', departmentName: 'Департамент документооборота и управления персоналом', email: 'hr.initiator@demo.local', homePath: '/hiring/requests' },
  'hr-director': { id: 'hr-director', name: 'Данияр Ахметов', role: 'Директор HR-департамента', departmentId: 'department-hr', departmentCode: 'HR', departmentName: 'Департамент документооборота и управления персоналом', email: 'hr.director@demo.local', homePath: '/hiring/inbox' },
  'economic-director': { id: 'economic-director', name: 'Алия Нуртаева', role: 'Директор экономического планирования', departmentId: 'department-economics', departmentCode: 'STRATEGY', departmentName: 'Департамент экономического планирования', email: 'economic.director@demo.local', homePath: '/hiring/inbox' },
  'commission-reviewer': { id: 'commission-reviewer', name: 'Представитель комиссии', role: 'Конкурсная комиссия', departmentId: 'commission', departmentCode: 'COMMISSION', departmentName: 'Конкурсная комиссия', email: 'commission@demo.local', homePath: '/hiring/inbox' },
  'legal-reviewer': { id: 'legal-reviewer', name: 'Марат Ибраев', role: 'Юридический департамент', departmentId: 'department-legal', departmentCode: 'LEGAL', departmentName: 'Юридический департамент', email: 'legal@demo.local', homePath: '/hiring/inbox' },
  'board-chairman': { id: 'board-chairman', name: 'Председатель правления', role: 'Председатель правления', departmentId: 'board', departmentCode: 'EXECUTIVE', departmentName: 'Правление', email: 'chairman@demo.local', homePath: '/hiring/inbox' },
  accountant: { id: 'accountant', name: 'Бухгалтер демо', role: 'Бухгалтер', departmentId: 'accounting', departmentCode: 'ACCOUNTING', departmentName: 'Бухгалтерия', email: 'accountant@demo.local', homePath: '/hiring/received' },
  'it-specialist': { id: 'it-specialist', name: 'IT-специалист демо', role: 'Специалист IT-отдела', departmentId: 'it', departmentCode: 'IT', departmentName: 'IT-отдел', email: 'it.specialist@demo.local', homePath: '/hiring/received' }
};

export const getPersonaProfile = (persona: PersonaId) => personaProfiles[persona];
