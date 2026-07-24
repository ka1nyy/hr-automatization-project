import { ArrowRight, CalendarCheck2, Network, UserMinus, UserPlus } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { PageHeader, Section } from '../../../shared/components';
import { RuleCallout } from '../components';
import { DEPARTMENTS } from '../data/hierarchy';
import { HIRING_STAGES } from '../data/hiring';
import { TERMINATION_STAGES } from '../data/termination';
import { LEAVE_STAGES } from '../data/leave';

interface SystemCard {
  to: string;
  icon: LucideIcon;
  eyebrow: string;
  title: string;
  description: string;
  stats: Array<{ value: string; label: string }>;
  tone: string;
}

const cards: SystemCard[] = [
  {
    to: '/hr/hierarchy',
    icon: Network,
    eyebrow: 'Организация',
    title: 'Иерархия ролей',
    description: 'Подчинение, департаменты, штатные единицы, матрица доступа и владельцы процессов.',
    stats: [
      { value: `${DEPARTMENTS.length}`, label: 'департаментов' },
      { value: '11', label: 'ролей доступа' },
      { value: '8', label: 'объектов прав' }
    ],
    tone: 'violet'
  },
  {
    to: '/hr/hiring',
    icon: UserPlus,
    eyebrow: 'Регламент найма',
    title: 'Система найма',
    description: 'От сигнала о потребности до испытательного срока: конкурсная комиссия и рубрика оценки.',
    stats: [
      { value: `${HIRING_STAGES.length}`, label: 'стадий' },
      { value: '9', label: 'ролей' },
      { value: '21', label: 'форма' }
    ],
    tone: 'teal'
  },
  {
    to: '/hr/terminations',
    icon: UserMinus,
    eyebrow: 'Регламент увольнения',
    title: 'Прекращение отношений',
    description: 'Основания R1–R9, доказательства, приказ, расчёт, отзыв доступов и архив дела.',
    stats: [
      { value: `${TERMINATION_STAGES.length}`, label: 'стадий' },
      { value: '9', label: 'маршрутов' },
      { value: '30', label: 'форм' }
    ],
    tone: 'coral'
  },
  {
    to: '/hr/leave',
    icon: CalendarCheck2,
    eyebrow: 'Регламент отпусков',
    title: 'Система отпусков',
    description: 'Планирование, заявление, приказ, оплата, замещение и возврат по 16 видам отпуска.',
    stats: [
      { value: `${LEAVE_STAGES.length}`, label: 'стадий' },
      { value: '16', label: 'видов' },
      { value: '30', label: 'форм' }
    ],
    tone: 'gold'
  }
];

const rollout: Array<{ step: number; result: string; participants: string }> = [
  { step: 1, result: 'Сверка структуры: дерево подразделений, двойные связи, руководители', participants: 'HR, руководство, корпоративный секретарь' },
  { step: 2, result: 'Загрузка штата: официальные должности, единицы, FTE, статусы, вакансии', participants: 'HR, ДЭП, бухгалтерия' },
  { step: 3, result: 'Профили должностей: функции, требования, замещение, ограничения', participants: 'Директора, HR, ЮД' },
  { step: 4, result: 'Матрица полномочий: решения, лимиты, согласования, подписи', participants: 'Руководство, ЮД, риск, комплаенс' },
  { step: 5, result: 'Модель доступа: роли, permissions, scopes, маскирование, аудит', participants: 'Владельцы данных, HR, IT, ИБ' },
  { step: 6, result: 'BPMN/DMN: версии процессов, условия, SLA, возвраты, эскалации', participants: 'Владельцы процессов, аналитик, разработчики' },
  { step: 7, result: 'Пилот: изменение штата → подбор → найм → доступы → увольнение', participants: 'HR, один департамент, IT, бухгалтерия' },
  { step: 8, result: 'Тиражирование: документы и отраслевые процессы', participants: 'Все подразделения' }
];

export default function WorkflowsOverviewPage() {
  return (
    <>
      <PageHeader
        eyebrow="АО «СПК «Ертіс» · HR Governance"
        title="Кадровые системы и регламенты"
        description="Единая витрина четырёх систем: иерархия ролей, найм, увольнение и отпуска. Модели построены по внутренним регламентам-проектам и служат картой для реализации ролей, маршрутов и Camunda-процессов."
      />
      <div className="wf-system-grid">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <Link key={card.to} to={card.to} className={`wf-system-card tone-${card.tone}`}>
              <span className="wf-system-icon"><Icon size={22} /></span>
              <small className="wf-system-eyebrow">{card.eyebrow}</small>
              <strong>{card.title}</strong>
              <p>{card.description}</p>
              <div className="wf-system-stats">
                {card.stats.map((stat) => <span key={stat.label}><b>{stat.value}</b>{stat.label}</span>)}
              </div>
              <span className="wf-system-cta">Открыть систему <ArrowRight size={15} /></span>
            </Link>
          );
        })}
      </div>

      <RuleCallout>
        Все модели — это проекты внутренних нормативных документов. Перед вводом в действие Юридический департамент сверяет актуальную редакцию законодательства, Устав, доверенности, коллективный и трудовые договоры, штатное расписание и правила оплаты труда.
      </RuleCallout>

      <Section title="Порядок утверждения и внедрения" meta="8 этапов до продуктивной эксплуатации">
        <div className="wf-rollout">
          {rollout.map((item) => (
            <article key={item.step} className="wf-rollout-step">
              <span className="wf-rollout-index">{item.step}</span>
              <div><strong>{item.result}</strong><small>{item.participants}</small></div>
            </article>
          ))}
        </div>
      </Section>
    </>
  );
}
