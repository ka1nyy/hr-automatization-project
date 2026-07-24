import { Section } from '../../shared/components';
import { ReferenceTable } from './components';
import type { ProcessSystemConfig } from './ProcessSystemPage';
import { HIRING_DOCUMENTS, HIRING_GATES, HIRING_META, HIRING_ROLES, HIRING_RUBRIC, HIRING_SCENARIOS, HIRING_STAGES, HIRING_STATUSES } from './data/hiring';
import {
  TERMINATION_DOCUMENTS,
  TERMINATION_GATES,
  TERMINATION_GROUNDS,
  TERMINATION_META,
  TERMINATION_ROLES,
  TERMINATION_ROUTES,
  TERMINATION_SETTLEMENT,
  TERMINATION_STAGES,
  TERMINATION_STATUSES
} from './data/termination';
import { LEAVE_DOCUMENTS, LEAVE_GATES, LEAVE_META, LEAVE_PAYMENT, LEAVE_PLANNING, LEAVE_ROLES, LEAVE_STAGES, LEAVE_STATUSES, LEAVE_TYPES } from './data/leave';
import { SICK_BENEFIT_STEPS, SICK_DOCUMENTS, SICK_GATES, SICK_META, SICK_NO_BENEFIT, SICK_ROLES, SICK_ROUTES, SICK_STAGES, SICK_STATUSES } from './data/sick';

export const hiringSystemConfig: ProcessSystemConfig = {
  meta: HIRING_META,
  stages: HIRING_STAGES,
  roles: HIRING_ROLES,
  gates: HIRING_GATES,
  statuses: HIRING_STATUSES,
  documents: HIRING_DOCUMENTS,
  extraTabs: [
    {
      id: 'rubric',
      label: 'Рубрика оценки',
      count: HIRING_RUBRIC.length,
      render: () => (
        <Section title="Система оценки конкурсной комиссии" meta={HIRING_META.quorum}>
          <ReferenceTable
            rows={HIRING_RUBRIC}
            columns={[
              { key: 'criterion', label: 'Критерий' },
              { key: 'weight', label: 'Вес' },
              { key: 'assesses', label: 'Что оценивается' },
              { key: 'assessor', label: 'Кто' }
            ]}
          />
        </Section>
      )
    },
    {
      id: 'scenarios',
      label: 'Сценарии',
      count: HIRING_SCENARIOS.length,
      render: () => (
        <Section title="Специальные сценарии найма" meta={`${HIRING_SCENARIOS.length} маршрутов`}>
          <ReferenceTable
            rows={HIRING_SCENARIOS}
            columns={[
              { key: 'scenario', label: 'Сценарий' },
              { key: 'route', label: 'Маршрут' },
              { key: 'rule', label: 'Жёсткое правило' }
            ]}
          />
        </Section>
      )
    }
  ]
};

export const terminationSystemConfig: ProcessSystemConfig = {
  meta: TERMINATION_META,
  stages: TERMINATION_STAGES,
  roles: TERMINATION_ROLES,
  gates: TERMINATION_GATES,
  statuses: TERMINATION_STATUSES,
  documents: TERMINATION_DOCUMENTS,
  extraTabs: [
    {
      id: 'routes',
      label: 'Маршруты R1–R9',
      count: TERMINATION_ROUTES.length,
      render: () => (
        <Section title="Справочник юридических маршрутов" meta="Основания прекращения по ТК РК">
          <ReferenceTable
            rows={TERMINATION_ROUTES}
            columns={[
              { key: 'code', label: 'Код' },
              { key: 'route', label: 'Маршрут' },
              { key: 'basis', label: 'Основание' },
              { key: 'minPackage', label: 'Минимальный пакет' }
            ]}
          />
        </Section>
      )
    },
    {
      id: 'grounds',
      label: 'Основания 52.x',
      count: TERMINATION_GROUNDS.length,
      render: () => (
        <Section title="Основания по инициативе работодателя" meta="Ст. 52 ТК РК · выборка">
          <ReferenceTable
            rows={TERMINATION_GROUNDS}
            columns={[
              { key: 'code', label: 'Код' },
              { key: 'event', label: 'Событие' },
              { key: 'evidence', label: 'Что должно лежать в деле' }
            ]}
          />
        </Section>
      )
    },
    {
      id: 'settlement',
      label: 'Расчёт',
      count: TERMINATION_SETTLEMENT.length,
      render: () => (
        <Section title="Расчёт и последний рабочий день" meta="Выплаты не позднее 3 рабочих дней">
          <ReferenceTable
            rows={TERMINATION_SETTLEMENT}
            columns={[
              { key: 'component', label: 'Компонент' },
              { key: 'rule', label: 'Правило' },
              { key: 'owner', label: 'Источник / владелец' }
            ]}
          />
        </Section>
      )
    }
  ]
};

export const leaveSystemConfig: ProcessSystemConfig = {
  meta: LEAVE_META,
  stages: LEAVE_STAGES,
  roles: LEAVE_ROLES,
  gates: LEAVE_GATES,
  statuses: LEAVE_STATUSES,
  documents: LEAVE_DOCUMENTS,
  extraTabs: [
    {
      id: 'types',
      label: 'Виды отпуска',
      count: LEAVE_TYPES.length,
      render: () => (
        <Section title="Справочник видов отпуска" meta="L01–L16 · выбор кода без свободного текста">
          <ReferenceTable
            rows={LEAVE_TYPES}
            columns={[
              { key: 'code', label: 'Код' },
              { key: 'title', label: 'Вид' },
              { key: 'basis', label: 'Основание' },
              { key: 'mode', label: 'Режим' }
            ]}
          />
        </Section>
      )
    },
    {
      id: 'planning',
      label: 'Планирование',
      count: LEAVE_PLANNING.length,
      render: () => (
        <Section title="Годовое планирование отпусков" meta="От открытия цикла до графика">
          <ReferenceTable
            rows={LEAVE_PLANNING.map((item) => ({ ...item, step: String(item.step) }))}
            columns={[
              { key: 'step', label: '№' },
              { key: 'action', label: 'Действие' },
              { key: 'owner', label: 'Владелец' },
              { key: 'result', label: 'Результат' }
            ]}
          />
        </Section>
      )
    },
    {
      id: 'payment',
      label: 'Оплата',
      count: LEAVE_PAYMENT.length,
      render: () => (
        <Section title="Расчёт, оплата и остатки" meta="Средний заработок по Приказу №908">
          <ReferenceTable
            rows={LEAVE_PAYMENT}
            columns={[
              { key: 'type', label: 'Вид' },
              { key: 'unit', label: 'Единица' },
              { key: 'calc', label: 'Расчёт' },
              { key: 'term', label: 'Срок' }
            ]}
          />
        </Section>
      )
    }
  ]
};

export const sickSystemConfig: ProcessSystemConfig = {
  meta: SICK_META,
  stages: SICK_STAGES,
  roles: SICK_ROLES,
  gates: SICK_GATES,
  statuses: SICK_STATUSES,
  documents: SICK_DOCUMENTS,
  extraTabs: [
    {
      id: 'routes',
      label: 'Маршруты S01–S18',
      count: SICK_ROUTES.length,
      render: () => (
        <Section title="Справочник маршрутов нетрудоспособности" meta="Лист / справка · вид документа определяет оплату">
          <ReferenceTable
            rows={SICK_ROUTES}
            columns={[
              { key: 'code', label: 'Код' },
              { key: 'scenario', label: 'Сценарий' },
              { key: 'basis', label: 'Основание' },
              { key: 'result', label: 'Результат' }
            ]}
          />
        </Section>
      )
    },
    {
      id: 'benefit',
      label: 'Расчёт пособия',
      count: SICK_BENEFIT_STEPS.length,
      render: () => (
        <Section title="Точный расчёт пособия" meta="MIN(средний дневной × рабочие дни; 25 × МРП)">
          <ReferenceTable
            rows={SICK_BENEFIT_STEPS}
            columns={[
              { key: 'step', label: 'Шаг' },
              { key: 'indicator', label: 'Показатель' },
              { key: 'rule', label: 'Правило' }
            ]}
          />
        </Section>
      )
    },
    {
      id: 'no-benefit',
      label: 'Без пособия',
      count: SICK_NO_BENEFIT.length,
      render: () => (
        <Section title="Когда пособие не выплачивается" meta="Ст. 133 ТК РК · обязательный контроль">
          <ReferenceTable
            rows={SICK_NO_BENEFIT}
            columns={[
              { key: 'code', label: 'Код' },
              { key: 'event', label: 'Случай' },
              { key: 'control', label: 'Обязательный контроль' }
            ]}
          />
        </Section>
      )
    }
  ]
};
