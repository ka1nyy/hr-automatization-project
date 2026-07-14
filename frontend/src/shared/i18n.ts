import type { Locale } from './types';

const dictionaries = {
  ru: {
    home: 'Главная', work: 'Моя работа', secretariat: 'Секретариат', incoming: 'Входящие', tasks: 'Задачи', processes: 'Процессы', organization: 'Организация', analytics: 'Аналитика', hr: 'HR пространство',
    search: 'Поиск документов, задач, сотрудников', create: 'Создать', incomingTitle: 'Входящая корреспонденция', register: 'Зарегистрировать письмо', allTasks: 'Единый центр задач', processCenter: 'Центр процессов', organizationTitle: 'Организация и назначения'
  },
  kk: {
    home: 'Басты бет', work: 'Менің жұмысым', secretariat: 'Хатшылық', incoming: 'Кіріс хаттар', tasks: 'Тапсырмалар', processes: 'Процестер', organization: 'Ұйым', analytics: 'Талдау', hr: 'HR кеңістігі',
    search: 'Құжаттар, тапсырмалар, қызметкерлер', create: 'Жасау', incomingTitle: 'Кіріс хат-хабарлар', register: 'Хатты тіркеу', allTasks: 'Бірыңғай тапсырмалар орталығы', processCenter: 'Процестер орталығы', organizationTitle: 'Ұйым және тағайындаулар'
  },
  en: {
    home: 'Home', work: 'My work', secretariat: 'Secretariat', incoming: 'Incoming', tasks: 'Tasks', processes: 'Processes', organization: 'Organization', analytics: 'Analytics', hr: 'HR workspace',
    search: 'Search documents, tasks, employees', create: 'Create', incomingTitle: 'Incoming correspondence', register: 'Register letter', allTasks: 'Unified task center', processCenter: 'Process center', organizationTitle: 'Organization and assignments'
  }
} as const;

export type TranslationKey = keyof typeof dictionaries.ru;
export const t = (locale: Locale, key: TranslationKey) => dictionaries[locale][key];

export const localeCode = (locale: Locale) => locale === 'ru' ? 'ru-RU' : locale === 'kk' ? 'kk-KZ' : 'en-US';
