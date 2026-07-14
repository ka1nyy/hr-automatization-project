import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, Blocks, Building2, CheckSquare2, ChevronDown, Command, FileInput, Gauge, Menu, Moon, PanelLeftClose, PanelLeftOpen, Plus, Search, Settings2, Sun, UsersRound, X } from 'lucide-react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { repositories } from '../repositories';
import { hrRepository } from '../features/hr/api';
import { getPermissions } from '../shared/permissions';
import { t } from '../shared/i18n';
import { useDeveloperStore } from '../shared/store';
import type { PersonaId } from '../shared/types';

type SearchResult = { id: string; title: string; detail: string; to: string; type: 'section' | 'document' | 'task' | 'employee' };

const personas: { id: PersonaId; name: string; role: string }[] = [
  { id: 'secretary', name: 'Алия Омарова', role: 'Секретарь' },
  { id: 'executive', name: 'Айдар Нурланов', role: 'Председатель Правления' },
  { id: 'employee', name: 'Мадина Садыкова', role: 'Главный эксперт' },
  { id: 'hr-specialist', name: 'Зарина Ахметова', role: 'HR специалист' },
  { id: 'process-designer', name: 'Диана Абилова', role: 'Процессный архитектор' }
];

export function AppShell() {
  const store = useDeveloperStore();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const searchInputRef = useRef<HTMLInputElement>(null);
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const currentPersona = personas.find((item) => item.id === store.persona)!;
  const canOpenHr = getPermissions(store.persona).includes('hr.read');
  const nav = useMemo(() => [
    { to: '/', icon: Gauge, label: t(store.locale, 'home'), end: true },
    { to: '/tasks', icon: CheckSquare2, label: t(store.locale, 'tasks'), badge: 5 },
    { to: '/correspondence/incoming', icon: FileInput, label: t(store.locale, 'incoming'), badge: 12 },
    { to: '/processes', icon: Blocks, label: t(store.locale, 'processes'), badge: 1 },
    { to: '/organization', icon: Building2, label: t(store.locale, 'organization') },
    ...(canOpenHr ? [{ to: '/departments/hr', icon: UsersRound, label: t(store.locale, 'hr') }] : [])
  ], [canOpenHr, store.locale]);
  const searchData = useQuery({
    queryKey: ['global-search', canOpenHr],
    enabled: searchOpen,
    queryFn: async () => {
      const [correspondence, tasks, employees] = await Promise.all([
        repositories.correspondence.listIncoming(),
        repositories.tasks.list(),
        canOpenHr ? hrRepository.listEmployees() : Promise.resolve([])
      ]);
      return { correspondence, tasks, employees };
    }
  });
  const searchResults = useMemo(() => {
    const sections: SearchResult[] = nav.map((item) => ({ id: `section-${item.to}`, title: item.label, detail: 'Раздел системы', to: item.to, type: 'section' }));
    const dataResults: SearchResult[] = [
      ...(searchData.data?.correspondence ?? []).map((item) => ({ id: `document-${item.id}`, title: item.subject, detail: `${item.number} · ${item.sender}`, to: `/correspondence/incoming/${item.id}`, type: 'document' as const })),
      ...(searchData.data?.tasks ?? []).map((item) => ({ id: `task-${item.id}`, title: item.title, detail: `${item.documentNumber} · ${item.process}`, to: '/tasks', type: 'task' as const })),
      ...(searchData.data?.employees ?? []).map((item) => ({ id: `employee-${item.id}`, title: item.fullName, detail: `${item.position} · ${item.department}`, to: `/departments/hr/employees/${item.id}`, type: 'employee' as const }))
    ];
    const normalized = searchQuery.trim().toLocaleLowerCase();
    const results = normalized ? [...sections, ...dataResults].filter((item) => `${item.title} ${item.detail}`.toLocaleLowerCase().includes(normalized)) : [...sections, ...dataResults];
    return results.slice(0, 8);
  }, [nav, searchData.data, searchQuery]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setSearchOpen(true);
      }
      if (event.key === 'Escape') setSearchOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  useEffect(() => {
    if (searchOpen) window.setTimeout(() => searchInputRef.current?.focus(), 0);
  }, [searchOpen]);

  const resetDatabase = async () => {
    await repositories.operations.reset();
    await hrRepository.reset();
    await queryClient.invalidateQueries();
  };

  const openSearch = () => {
    setNotificationsOpen(false);
    setSearchOpen(true);
  };

  const selectSearchResult = (result: SearchResult) => {
    navigate(result.to);
    setSearchOpen(false);
    setSearchQuery('');
  };

  return (
    <div className={`operations-shell ${store.sidebarCollapsed ? 'is-collapsed' : ''}`}>
      <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`}>
        <div className="product-mark">
          <span className="mark-glyph"><i /><i /><i /></span>
          {!store.sidebarCollapsed && <span><strong>ERTIS</strong><small>OPERATIONS</small></span>}
          <button className="icon-button mobile-close" onClick={() => setMobileOpen(false)} aria-label="Закрыть меню"><X size={18} /></button>
        </div>
        {!store.sidebarCollapsed && <button className="organization-switch"><span className="org-monogram">СПК</span><span><strong>АО «СПК «Ертіс»</strong><small>Корпоративный офис</small></span><ChevronDown size={14} /></button>}
        <nav className="primary-nav" aria-label="Основная навигация">
          {!store.sidebarCollapsed && <span className="nav-label">Рабочее пространство</span>}
          {nav.map(({ to, icon: Icon, label, badge, end }) => <NavLink key={to} to={to} end={end} onClick={() => setMobileOpen(false)} title={label}><Icon size={18} /><span>{label}</span>{badge && <b>{badge}</b>}</NavLink>)}
          {!store.sidebarCollapsed && <span className="nav-label nav-label-spaced">Контроль</span>}
          <button onClick={store.toggleDeveloper} title="Developer toolbar"><Settings2 size={18} /><span>Developer tools</span><i className="live-dot" /></button>
        </nav>
        <div className="sidebar-footer">
          <button className="persona-card" onClick={store.toggleDeveloper} title="Сменить персону"><span className="avatar">{currentPersona.name.split(' ').map((v) => v[0]).join('').slice(0, 2)}</span>{!store.sidebarCollapsed && <span><strong>{currentPersona.name}</strong><small>{currentPersona.role}</small></span>}</button>
          <button className="icon-button collapse-button" onClick={store.toggleSidebar} aria-label="Свернуть боковую панель">{store.sidebarCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}</button>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="topbar-inner">
            <div className="topbar-left"><button className="icon-button mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Открыть меню"><Menu size={20} /></button><div className="breadcrumbs"><span>АО «СПК «Ертіс»</span><b>/</b><strong>{location.pathname.includes('/departments/hr') ? 'Департамент управления персоналом' : location.pathname.includes('incoming') ? 'Входящая корреспонденция' : location.pathname.includes('tasks') ? 'Моя работа' : location.pathname.includes('processes') ? 'Процессы' : location.pathname.includes('organization') ? 'Организация' : 'Главная'}</strong></div></div>
            <button className="global-search" onClick={openSearch} aria-label="Глобальный поиск"><Search size={17} /><span>{t(store.locale, 'search')}</span><kbd><Command size={12} /> K</kbd></button>
            <div className="topbar-actions"><button className="create-button" onClick={() => navigate(location.pathname.includes('/departments/hr') ? '/departments/hr/leave' : '/correspondence/incoming/new')}><Plus size={17} />{t(store.locale, 'create')}</button><button className="icon-button theme-button" onClick={() => store.setTheme(store.theme === 'dark' ? 'light' : 'dark')} aria-label="Переключить тему">{store.theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}</button><div className="notification-wrap"><button className="icon-button notification-button" onClick={() => setNotificationsOpen(!notificationsOpen)} aria-label="Уведомления"><Bell size={18} /><i /></button>{notificationsOpen && <div className="popover notification-popover"><div className="popover-head"><strong>Уведомления</strong><span>3 новых</span></div><div className="notification-item"><i className="tone-coral" /><span><strong>Срок задачи истёк</strong><small>ВХ-2026-000839 · 24 мин назад</small></span></div><div className="notification-item"><i className="tone-gold" /><span><strong>Документ ожидает подписи</strong><small>Ответ по реестру имущества</small></span></div><div className="notification-item"><i className="tone-violet" /><span><strong>Новая задача соисполнителя</strong><small>Юридическое заключение</small></span></div></div>}</div></div>
          </div>
        </header>
        <main className="content"><Outlet /></main>
      </div>

      {searchOpen && <div className="search-overlay" onMouseDown={() => setSearchOpen(false)}><section className="search-dialog" role="dialog" aria-modal="true" aria-label="Глобальный поиск" onMouseDown={(event) => event.stopPropagation()}><div className="search-input-wrap"><Search size={18} /><input ref={searchInputRef} value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Поиск документов, задач, сотрудников" /><kbd>Esc</kbd></div><div className="search-results">{searchResults.length ? searchResults.map((result) => <button key={result.id} onClick={() => selectSearchResult(result)}><span className={`search-result-icon ${result.type}`}>{result.type === 'document' ? <FileInput size={16} /> : result.type === 'employee' ? <UsersRound size={16} /> : result.type === 'task' ? <CheckSquare2 size={16} /> : <Gauge size={16} />}</span><span><strong>{result.title}</strong><small>{result.detail}</small></span></button>) : <p className="search-state">{searchData.isLoading ? 'Загрузка результатов...' : 'Ничего не найдено. Попробуйте изменить запрос.'}</p>}</div><footer><span>{searchQuery ? `${searchResults.length} результатов` : 'Начните вводить запрос или выберите раздел'}</span><kbd><Command size={11} /> K</kbd></footer></section></div>}

      {store.developerOpen && <aside className="developer-panel" aria-label="Developer toolbar">
        <div className="developer-head"><span><i className="live-dot" /> Developer workspace</span><button className="icon-button" onClick={store.toggleDeveloper}><X size={18} /></button></div>
        <label>Текущая персона<select value={store.persona} onChange={(e) => store.setPersona(e.target.value as PersonaId)}>{personas.map((item) => <option key={item.id} value={item.id}>{item.role}</option>)}</select></label>
        <label>Сценарий<select value={store.scenario} onChange={(e) => store.setScenario(e.target.value)}><option value="normal">Обычная работа</option><option value="morning">Утренняя очередь</option><option value="incident">Инцидент процесса</option><option value="restricted">Закрытые документы</option></select></label>
        <div className="developer-grid"><div><span>DATA</span><strong>{store.dataMode}</strong></div><div><span>WORKFLOW</span><strong>{store.workflowMode}</strong></div><div><span>SIGNATURE</span><strong>{store.signatureMode}</strong></div><div><span>API</span><strong className="status-ok">mock ready</strong></div></div>
        <label>Язык<select value={store.locale} onChange={(e) => store.setLocale(e.target.value as 'ru' | 'kk' | 'en')}><option value="ru">Русский</option><option value="kk">Қазақша</option><option value="en">English</option></select></label>
        <div className="permission-list"><span>Активные разрешения</span>{getPermissions(store.persona).map((permission) => <code key={permission}>{permission}</code>)}</div>
        <button className="secondary-button full" onClick={resetDatabase}>Сбросить mock-базу</button>
        <p>Frontend checks only affect presentation. Production authorization must be enforced by backend services.</p>
      </aside>}
    </div>
  );
}
