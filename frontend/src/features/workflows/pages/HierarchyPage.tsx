import { useState } from 'react';
import { Building2, Layers, Lock, Network, ScrollText, ShieldCheck, Database } from 'lucide-react';
import { PageHeader, Section } from '../../../shared/components';
import { MetricRow, ReferenceTable, RuleCallout, SegmentTabs } from '../components';
import {
  ACCESS_MATRIX,
  BASE_HEADCOUNT,
  DATA_ENTITIES,
  DEPARTMENTS,
  HIERARCHY_TIERS,
  LEADERSHIP,
  PERMISSION_CATALOG,
  PROCESS_OWNERS,
  STAFFING_SLOT_FIELDS,
  type UnitStatus
} from '../data/hierarchy';

const statusLabel: Record<UnitStatus, string> = { confirmed: 'Подтверждено', model: 'Модель', needs_document: 'Нужен документ' };

export default function HierarchyPage() {
  const [tab, setTab] = useState('tree');
  const [selected, setSelected] = useState(DEPARTMENTS[0].code);
  const department = DEPARTMENTS.find((item) => item.code === selected) ?? DEPARTMENTS[0];

  return (
    <>
      <PageHeader
        eyebrow="Организация · Рабочая модель иерархии"
        title="Иерархия ролей и штатных единиц"
        description="Подчинение, функции, полномочия, доступы на сайте и владельцы процессов АО «СПК «Ертіс». Базовая численность — расчётный сценарий, а не утверждённое штатное расписание."
      />
      <MetricRow
        items={[
          { label: 'Департаментов', value: DEPARTMENTS.length, hint: '8 профильных + бухгалтерия', tone: 'violet' },
          { label: 'Штатных единиц (сценарий)', value: BASE_HEADCOUNT, hint: 'база для проектирования', tone: 'teal' },
          { label: 'Ролей в матрице доступа', value: ACCESS_MATRIX.length, hint: 'RBAC × область × срок', tone: 'gold' },
          { label: 'Объектов прав', value: PERMISSION_CATALOG.length, hint: 'каталог разрешений', tone: 'coral' }
        ]}
      />
      <SegmentTabs
        tabs={[
          { id: 'tree', label: 'Иерархия' },
          { id: 'departments', label: 'Департаменты', count: DEPARTMENTS.length },
          { id: 'staffing', label: 'Штатная единица' },
          { id: 'access', label: 'Матрица доступа', count: ACCESS_MATRIX.length },
          { id: 'permissions', label: 'Права', count: PERMISSION_CATALOG.length },
          { id: 'owners', label: 'Процессы', count: PROCESS_OWNERS.length },
          { id: 'model', label: 'Модель данных', count: DATA_ENTITIES.length }
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === 'tree' && (
        <>
          <Section title="Управленческая вертикаль" meta="Подтверждённые связи из положений">
            <div className="wf-legend"><Network size={15} /> Коллегиальные органы не считаются штатными единицами; члены органов могут занимать штатные должности.</div>
            <div className="wf-tree">
              {HIERARCHY_TIERS.map((tier) => (
                <div className="wf-tier" key={tier.tier}>
                  <span className="wf-tier-label">{tier.tier}</span>
                  <div className="wf-tier-nodes">
                    {tier.nodes.map((node) => <span className="wf-node" key={node}>{node}</span>)}
                  </div>
                </div>
              ))}
            </div>
          </Section>
          <Section title="Руководство и независимые функции" meta="Часть требует отдельных документов">
            <div className="wf-lead-grid">
              {LEADERSHIP.map((unit) => (
                <article key={unit.title} className="wf-lead-card">
                  <header><strong>{unit.title}</strong><span className={`wf-badge status-${unit.status}`}>{statusLabel[unit.status]}</span></header>
                  <p>{unit.mandate}</p>
                  <footer><b>×{unit.base}</b><small>{unit.source}</small></footer>
                </article>
              ))}
            </div>
            <RuleCallout>Независимые контрольные функции нельзя административно подчинять операционному подразделению ради удобства интерфейса — для них создаются отдельные роли, область видимости и маршруты эскалации.</RuleCallout>
          </Section>
        </>
      )}

      {tab === 'departments' && (
        <div className="wf-dept-layout">
          <Section title="Департаменты" meta={`${DEPARTMENTS.length} подразделений`}>
            <div className="wf-dept-list">
              {DEPARTMENTS.map((item) => (
                <button key={item.code} className={`wf-dept-item ${selected === item.code ? 'active' : ''}`} onClick={() => setSelected(item.code)}>
                  <span className="wf-dept-code">{item.code}</span>
                  <span><strong>{item.name}</strong><small>{item.units} единиц (сценарий)</small></span>
                </button>
              ))}
            </div>
          </Section>
          <div className="wf-dept-detail">
            <Section title={department.name} meta={`${department.code} · ${department.units} единиц`}>
              <div className="wf-dept-meta">
                <div><small>Подчинение</small><strong>{department.subordination}</strong></div>
                <div><small>Руководитель</small><strong>{department.head}</strong></div>
                <div><small>Область данных</small><strong>{department.dataScope}</strong></div>
              </div>
              <div className="wf-dept-columns">
                <div>
                  <h3><Building2 size={15} /> Задачи и функции</h3>
                  <ul className="wf-bullet">{department.functions.map((fn) => <li key={fn}>{fn}</li>)}</ul>
                </div>
                <div>
                  <h3><ShieldCheck size={15} /> Взаимодействие</h3>
                  <div className="wf-chip-row">{department.interactsWith.map((entity) => <span key={entity} className="wf-chip">{entity}</span>)}</div>
                </div>
              </div>
              <h3 className="wf-subhead"><Layers size={15} /> Проектные должности</h3>
              <ReferenceTable
                rows={department.positions.map((position) => ({ ...position, base: `×${position.base}`, status: statusLabel[position.status] }))}
                columns={[
                  { key: 'role', label: 'Должность' },
                  { key: 'base', label: 'База' },
                  { key: 'status', label: 'Статус' },
                  { key: 'duties', label: 'Обязанности' },
                  { key: 'access', label: 'Доступ на сайте' }
                ]}
              />
            </Section>
          </div>
        </div>
      )}

      {tab === 'staffing' && (
        <Section title="Что такое штатная единица в системе" meta="Основа для ролей и экранов">
          <div className="wf-legend"><Layers size={15} /> Директор департамента не создаёт единицу сам: инициирует заявку, HR проверяет структуру, ДЭП — бюджет, ЮД — решение, уполномоченный орган утверждает, HR публикует версию.</div>
          <ReferenceTable
            rows={STAFFING_SLOT_FIELDS}
            columns={[
              { key: 'field', label: 'Поле' },
              { key: 'content', label: 'Содержание' }
            ]}
          />
        </Section>
      )}

      {tab === 'access' && (
        <Section title="Матрица ролей и полномочий сайта" meta="Доступ = роль × организация × подразделение × объект × этап × срок">
          <div className="wf-legend"><Lock size={15} /> Название должности само по себе не является достаточным основанием для доступа.</div>
          <ReferenceTable
            rows={ACCESS_MATRIX}
            columns={[
              { key: 'role', label: 'Роль' },
              { key: 'scope', label: 'Область' },
              { key: 'sees', label: 'Видит' },
              { key: 'hidden', label: 'Запрещено' }
            ]}
          />
        </Section>
      )}

      {tab === 'permissions' && (
        <Section title="Каталог базовых разрешений" meta="RBAC-атомы для объектов">
          <div className="wf-perm-grid">
            {PERMISSION_CATALOG.map((group) => (
              <article key={group.object} className="wf-perm-card">
                <strong>{group.object}</strong>
                <div className="wf-chip-row">{group.permissions.map((permission) => <code key={permission}>{permission}</code>)}</div>
              </article>
            ))}
          </div>
        </Section>
      )}

      {tab === 'owners' && (
        <Section title="Владельцы основных бизнес-процессов" meta={`${PROCESS_OWNERS.length} процессов`}>
          <div className="wf-legend"><ScrollText size={15} /> HR владеет кадровыми процессами; независимые функции подключаются как согласующие.</div>
          <ReferenceTable
            rows={PROCESS_OWNERS}
            columns={[
              { key: 'process', label: 'Процесс' },
              { key: 'owner', label: 'Владелец' },
              { key: 'start', label: 'Старт' },
              { key: 'result', label: 'Основной результат' },
              { key: 'participants', label: 'Ключевые участники' }
            ]}
          />
        </Section>
      )}

      {tab === 'model' && (
        <Section title="Обязательная модель данных платформы" meta={`${DATA_ENTITIES.length} сущностей`}>
          <div className="wf-legend"><Database size={15} /> Роль не равна должности; опубликованные версии и подписанные документы неизменяемы.</div>
          <ReferenceTable
            rows={DATA_ENTITIES}
            columns={[
              { key: 'entity', label: 'Сущность' },
              { key: 'purpose', label: 'Назначение' },
              { key: 'constraint', label: 'Ключевые связи / ограничения' }
            ]}
          />
        </Section>
      )}
    </>
  );
}
