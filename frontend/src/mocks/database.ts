import type { Correspondence, Employee, ProcessDefinition, WorkTask } from '../shared/types';

const now = '2026-07-14T09:30:00.000Z';

export const seedCorrespondence: Correspondence[] = [
  {
    id: 'inc-842', number: 'ВХ-2026-000842', sender: 'Министерство труда и социальной защиты РК', senderNumber: '12-4/1842', senderDate: '2026-07-10', receivedAt: '2026-07-14T08:42:00.000Z',
    subject: 'О предоставлении сведений по реализации социальных проектов за II квартал', summary: 'Запрошен консолидированный отчёт по проектам с разбивкой по регионам и сроком ответа до 17 июля.', documentType: 'Официальный запрос', channel: 'Государственный портал', department: 'Стратегия и аналитика', executive: 'А. С. Нурланов', executor: 'М. К. Садыкова', dueDate: '2026-07-17', priority: 'urgent', status: 'execution', workflowStep: 'Сбор заключений', confidentiality: 'internal', responseRequired: true,
    attachments: [{ id: 'a1', name: 'Запрос_12-4-1842.pdf', size: '2.4 МБ', kind: 'scan' }, { id: 'a2', name: 'Форма_отчёта.xlsx', size: '184 КБ', kind: 'attachment' }], tags: ['госорган', 'отчётность', 'Q2'],
    audit: [
      { id: 'e1', at: '2026-07-14T08:42:00.000Z', actor: 'Алия Омарова', action: 'Зарегистрировано', detail: 'Присвоен номер ВХ-2026-000842' },
      { id: 'e2', at: '2026-07-14T09:05:00.000Z', actor: 'А. С. Нурланов', action: 'Создана резолюция', detail: 'Основной исполнитель и 2 соисполнителя' },
      { id: 'e3', at: now, actor: 'Workflow Gateway', action: 'Созданы задачи', detail: 'Стратегия, Юридический, Экономическое планирование' }
    ]
  },
  {
    id: 'inc-841', number: 'ВХ-2026-000841', sender: 'ТОО «QazTech Infrastructure»', senderNumber: 'QT-778/26', senderDate: '2026-07-11', receivedAt: '2026-07-14T08:18:00.000Z', subject: 'Согласование дополнительного соглашения к договору поставки', summary: 'Контрагент направил проект дополнительного соглашения с изменением графика поставки.', documentType: 'Договорная переписка', channel: 'Email', department: 'Юридический департамент', executive: 'Д. Р. Исмаилов', executor: 'Е. Т. Ким', dueDate: '2026-07-16', priority: 'high', status: 'approval', workflowStep: 'Юридическое согласование', confidentiality: 'internal', responseRequired: true, attachments: [{ id: 'a3', name: 'Письмо_QT-778.pdf', size: '1.1 МБ', kind: 'scan' }, { id: 'a4', name: 'Допсоглашение_v3.docx', size: '286 КБ', kind: 'attachment' }], tags: ['договор', 'поставка'], audit: [{ id: 'e4', at: '2026-07-14T08:18:00.000Z', actor: 'Дина Жакупова', action: 'Зарегистрировано', detail: 'Присвоен номер ВХ-2026-000841' }]
  },
  {
    id: 'inc-840', number: 'ВХ-2026-000840', sender: 'АО «НК «Kazakh Invest»', senderNumber: 'KI-04-921', senderDate: '2026-07-09', receivedAt: '2026-07-13T17:24:00.000Z', subject: 'Приглашение к участию в инвестиционном форуме', summary: 'Предлагается определить состав делегации и представить перечень проектов.', documentType: 'Приглашение', channel: 'ЭДО', department: 'Инвестиционный департамент', executive: 'А. С. Нурланов', executor: 'Р. А. Серикбаев', dueDate: '2026-07-22', priority: 'normal', status: 'resolution', workflowStep: 'Резолюция руководителя', confidentiality: 'public', responseRequired: true, attachments: [{ id: 'a5', name: 'Invitation.pdf', size: '824 КБ', kind: 'scan' }], tags: ['инвестиции', 'форум'], audit: [{ id: 'e5', at: '2026-07-13T17:24:00.000Z', actor: 'Алия Омарова', action: 'Направлено на резолюцию', detail: 'Председателю Правления' }]
  },
  {
    id: 'inc-839', number: 'ВХ-2026-000839', sender: 'Комитет государственного имущества', senderNumber: 'КГИ-5/331', senderDate: '2026-07-08', receivedAt: '2026-07-13T15:10:00.000Z', subject: 'Актуализация реестра объектов государственного имущества', summary: 'Необходимо подтвердить сведения по 18 объектам.', documentType: 'Поручение', channel: 'Государственный портал', department: 'Управление активами', executive: 'Д. Р. Исмаилов', executor: 'С. Б. Нуртаев', dueDate: '2026-07-15', priority: 'urgent', status: 'signature', workflowStep: 'Подписание ЭЦП', confidentiality: 'internal', responseRequired: true, attachments: [{ id: 'a6', name: 'Реестр.pdf', size: '3.8 МБ', kind: 'scan' }, { id: 'a7', name: 'Объекты.xlsx', size: '94 КБ', kind: 'attachment' }], tags: ['активы'], audit: [{ id: 'e6', at: '2026-07-13T15:10:00.000Z', actor: 'Дина Жакупова', action: 'Согласовано', detail: 'Ожидает подписи' }]
  },
  {
    id: 'inc-838', number: 'ВХ-2026-000838', sender: 'Акимат Карагандинской области', senderNumber: '02-18/1409', senderDate: '2026-07-07', receivedAt: '2026-07-13T13:45:00.000Z', subject: 'О ходе строительства социального объекта', summary: 'Предоставление обновлённого графика строительно-монтажных работ.', documentType: 'Информационное письмо', channel: 'Курьер', department: 'Строительный департамент', executive: 'Л. К. Абдрахманова', executor: 'Н. А. Тлеубаев', dueDate: '2026-07-20', priority: 'normal', status: 'dispatch', workflowStep: 'Отправка секретариатом', confidentiality: 'public', responseRequired: true, attachments: [{ id: 'a8', name: 'Письмо.pdf', size: '1.7 МБ', kind: 'scan' }], tags: ['строительство'], audit: [{ id: 'e7', at: '2026-07-13T13:45:00.000Z', actor: 'Workflow Gateway', action: 'Ответ подписан', detail: 'Ожидает исходящего номера' }]
  }
];

export const seedTasks: WorkTask[] = [
  { id: 't-101', title: 'Подготовить сводный ответ по социальным проектам', documentNumber: 'ВХ-2026-000842', process: 'Обработка входящего письма', role: 'Основной исполнитель', department: 'Стратегия и аналитика', dueDate: '2026-07-17', priority: 'urgent', state: 'claimed', assignee: 'М. К. Садыкова' },
  { id: 't-102', title: 'Предоставить юридическое заключение', documentNumber: 'ВХ-2026-000842', process: 'Обработка входящего письма', role: 'Соисполнитель', department: 'Юридический департамент', dueDate: '2026-07-15', priority: 'high', state: 'available' },
  { id: 't-103', title: 'Проверить финансовые показатели отчёта', documentNumber: 'ВХ-2026-000842', process: 'Обработка входящего письма', role: 'Соисполнитель', department: 'Экономическое планирование', dueDate: '2026-07-15', priority: 'high', state: 'available' },
  { id: 't-104', title: 'Согласовать дополнительное соглашение', documentNumber: 'ВХ-2026-000841', process: 'Договорная переписка', role: 'Согласующий', department: 'Юридический департамент', dueDate: '2026-07-16', priority: 'high', state: 'claimed', assignee: 'Е. Т. Ким' },
  { id: 't-105', title: 'Подписать ответ по реестру имущества', documentNumber: 'ВХ-2026-000839', process: 'Исходящий ответ', role: 'Подписант', department: 'Руководство', dueDate: '2026-07-14', priority: 'urgent', state: 'overdue' }
];

export const seedProcesses: ProcessDefinition[] = [
  { id: 'p-hr-leave', name: 'Согласование отпуска', version: 5, state: 'published', activeInstances: 9, owner: 'Департамент управления персоналом', updatedAt: '2026-07-14', steps: ['Заявка', 'Руководитель', 'Проверка HR', 'Приказ', 'Календарь'] },
  { id: 'p-hr-change', name: 'Изменение данных сотрудника', version: 2, state: 'published', activeInstances: 4, owner: 'Департамент управления персоналом', updatedAt: '2026-07-12', steps: ['Инициирование', 'Проверка HR', 'Согласование', 'Обновление HR Core'] },
  { id: 'p-hr-onboarding', name: 'Адаптация сотрудника', version: 3, state: 'published', activeInstances: 7, owner: 'Департамент управления персоналом', updatedAt: '2026-07-10', steps: ['План адаптации', 'Доступы', 'Рабочее место', 'Контрольная встреча'] },
  { id: 'p-incoming', name: 'Обработка входящей корреспонденции', version: 7, state: 'published', activeInstances: 48, owner: 'Секретариат', updatedAt: '2026-07-11', steps: ['Регистрация', 'Резолюция', 'Исполнение', 'Согласование', 'ЭЦП', 'Отправка'] },
  { id: 'p-contract', name: 'Согласование договорной переписки', version: 4, state: 'published', activeInstances: 19, owner: 'Юридический департамент', updatedAt: '2026-07-09', steps: ['Автор', 'Директор', 'Экономика', 'Юристы', 'Риск', 'Подписание'] },
  { id: 'p-invest', name: 'Инвестиционное заключение', version: 3, state: 'draft', activeInstances: 0, owner: 'Инвестиционный департамент', updatedAt: '2026-07-14', steps: ['Инициатор', 'Аналитик', 'Экономика', 'Риск', 'Комитет'] },
  { id: 'p-dispatch', name: 'Регистрация и отправка ответа', version: 6, state: 'incident', activeInstances: 7, owner: 'Секретариат', updatedAt: '2026-07-14', steps: ['Проверка подписи', 'Нумерация', 'Отправка', 'Закрытие'] }
];

export const seedEmployees: Employee[] = [
  { id: 'e-1', name: 'Алия Омарова', initials: 'АО', role: 'Секретарь', department: 'Секретариат', candidateGroups: ['secretariat-registrars', 'dispatch-operators'], status: 'active' },
  { id: 'e-2', name: 'Айдар Нурланов', initials: 'АН', role: 'Председатель Правления', department: 'Руководство', candidateGroups: ['executive-resolution', 'authorized-signatories'], status: 'active' },
  { id: 'e-3', name: 'Мадина Садыкова', initials: 'МС', role: 'Главный эксперт', department: 'Стратегия и аналитика', candidateGroups: ['strategy-executors'], status: 'active' },
  { id: 'e-4', name: 'Елена Ким', initials: 'ЕК', role: 'Юрисконсульт', department: 'Юридический департамент', candidateGroups: ['legal-contract-reviewers'], status: 'active' },
  { id: 'e-5', name: 'Руслан Ибраев', initials: 'РИ', role: 'Директор департамента', department: 'Экономическое планирование', candidateGroups: ['economic-approvers'], status: 'acting' },
  { id: 'e-6', name: 'Диана Абилова', initials: 'ДА', role: 'Процессный архитектор', department: 'Цифровая трансформация', candidateGroups: ['process-designers', 'process-testers'], status: 'active' }
];
