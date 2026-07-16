export type PlannedEventKind = 'leave' | 'sick' | 'hiring' | 'dismissal' | 'approval' | 'document';

export type PlannedEvent = {
  id: string;
  title: string;
  person: string;
  date: string;
  endDate?: string;
  kind: PlannedEventKind;
  status: 'planned' | 'review' | 'approved' | 'attention';
  detail: string;
};

export type PlannedNotification = {
  id: string;
  title: string;
  detail: string;
  time: string;
  unread: boolean;
};

// Temporary frontend data. Replace this service with an API adapter when a matching backend module exists.
const events: PlannedEvent[] = [
  { id: 'cal-1', title: 'Ежегодный отпуск', person: 'Мадина Садыкова', date: '2026-07-20', endDate: '2026-07-31', kind: 'leave', status: 'approved', detail: '10 рабочих дней' },
  { id: 'cal-2', title: 'Больничный', person: 'Алексей Ким', date: '2026-07-16', endDate: '2026-07-18', kind: 'sick', status: 'attention', detail: 'Ожидается лист нетрудоспособности' },
  { id: 'cal-3', title: 'Выход на работу', person: 'Данияр Сатпаев', date: '2026-07-22', kind: 'hiring', status: 'planned', detail: 'Департамент инвестиций' },
  { id: 'cal-4', title: 'Последний рабочий день', person: 'Ирина Волкова', date: '2026-07-28', kind: 'dismissal', status: 'review', detail: 'Обходной лист: 4 из 6 шагов' },
  { id: 'cal-5', title: 'Согласование приказа', person: 'Зарина Ахметова', date: '2026-07-17', kind: 'approval', status: 'review', detail: 'Этап 2 из 3 · Руководитель' },
  { id: 'cal-6', title: 'Личное дело', person: 'Алия Омарова', date: '2026-07-19', kind: 'document', status: 'attention', detail: 'Не хватает копии диплома' },
];

const notifications: PlannedNotification[] = [
  { id: 'note-1', title: 'Новая заявка на отпуск', detail: 'Мадина Садыкова · нужна проверка HR', time: '10 мин', unread: true },
  { id: 'note-2', title: 'Неполное личное дело', detail: 'Алия Омарова · 82% документов', time: '1 ч', unread: true },
  { id: 'note-3', title: 'Структура опубликована', detail: 'Версия 12 вступит в силу 1 августа', time: 'Вчера', unread: false },
];

export const plannedHrService = {
  async listEvents() { return events; },
  async listNotifications() { return notifications; },
};
