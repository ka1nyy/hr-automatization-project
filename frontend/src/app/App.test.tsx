import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useDeveloperStore } from '../shared/store';
import { App } from './App';

function renderRoute(route: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[route]}><App /></MemoryRouter></QueryClientProvider>);
}

describe('application runtime', () => {
  beforeEach(() => {
    localStorage.clear();
    useDeveloperStore.setState({ persona: 'secretary' });
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: [], meta: { requestId: 'test-request' } })
    }));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('opens directly in the operations workspace without authentication', () => {
    renderRoute('/');
    expect(screen.getByRole('navigation', { name: 'Основная навигация' })).toBeTruthy();
    expect(screen.queryByText(/войти|login/i)).toBeNull();
  });

  it('opens the global search dialog from the header', async () => {
    renderRoute('/');
    fireEvent.click(screen.getByLabelText('Глобальный поиск'));

    expect(await screen.findByRole('dialog', { name: 'Глобальный поиск' })).toBeTruthy();
    const input = screen.getByPlaceholderText('Поиск документов, задач, сотрудников');
    fireEvent.change(input, { target: { value: 'Задачи' } });
    expect(await screen.findByRole('button', { name: /Задачи.*Раздел системы/i })).toBeTruthy();
  });

  it('opens the employee directory for the HR specialist persona', async () => {
    useDeveloperStore.setState({ persona: 'hr-specialist' });
    renderRoute('/departments/hr/employees');

    expect(await screen.findByRole('heading', { name: 'Сотрудники' }, { timeout: 5000 })).toBeTruthy();
    expect(screen.getByText('Зарина Ахметова')).toBeTruthy();
  });

  it('opens the HR department workspace on the main page after HR login', async () => {
    useDeveloperStore.setState({ persona: 'hr-specialist' });
    renderRoute('/');

    expect(await screen.findByRole('heading', { name: 'Рабочее пространство' }, { timeout: 5000 })).toBeTruthy();
    expect(screen.getByText('HR', { selector: '.breadcrumbs span' })).toBeTruthy();
    expect(screen.getByText('Главная', { selector: '.breadcrumbs strong' })).toBeTruthy();
    expect(screen.getAllByRole('link', { name: /Входящие сообщения/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: /^Сотрудники$/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: /^Процессы/i }).length).toBeGreaterThan(0);
    expect(screen.getByRole('img', { name: 'Распределение сотрудников по типу присутствия' })).toBeTruthy();
    expect(screen.getByRole('group', { name: 'HR-показатели, требующие контроля' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Что требует вашего внимания' })).toBeTruthy();
    expect(screen.getByText('1. Разобрать входящие')).toBeTruthy();
    expect(screen.getByText('2. Выполнить задачи')).toBeTruthy();
    expect(screen.getByText('3. Принять решения')).toBeTruthy();
    expect(screen.queryByRole('heading', { name: 'СОТРУДНИКИ И ОТСУТСТВИЯ' })).toBeNull();
    expect(screen.queryByText(/Операционный день|Сводка дня|HR пространство/i)).toBeNull();
  });

  it('keeps shared messages and processes inside the HR department context', async () => {
    useDeveloperStore.setState({ persona: 'hr-specialist' });
    const view = renderRoute('/correspondence/incoming');
    expect(await screen.findByRole('heading', { name: 'Входящие сообщения' })).toBeTruthy();
    expect(screen.getByRole('tablist', { name: 'Категории сообщений' })).toBeTruthy();
    expect(screen.getByText('HR', { selector: '.breadcrumbs span' })).toBeTruthy();

    view.unmount();
    renderRoute('/processes');
    expect(await screen.findByRole('heading', { name: 'Процессы' })).toBeTruthy();
    expect((await screen.findAllByText('Согласование отпуска')).length).toBeGreaterThan(0);
    expect(screen.queryByText('Обработка входящей корреспонденции')).toBeNull();
  });

  it('shows the unified HR workspace and directory to an employee persona', async () => {
    useDeveloperStore.setState({ persona: 'employee' });
    const view = renderRoute('/');
    expect(await screen.findByRole('heading', { name: 'Рабочее пространство' })).toBeTruthy();
    expect(screen.getByText('HR', { selector: '.breadcrumbs span' })).toBeTruthy();

    view.unmount();
    renderRoute('/departments/hr/employees');
    expect(await screen.findByRole('heading', { name: 'Сотрудники' })).toBeTruthy();
  });

  it('shows dynamic HR context and streamlined Add Employee actions', async () => {
    useDeveloperStore.setState({ persona: 'hr-specialist' });
    renderRoute('/hr/hiring/add-employee');

    expect(await screen.findByRole('heading', { name: 'Регистрация сотрудника' })).toBeTruthy();
    expect(screen.getByText('Регистрация сотрудника', { selector: '.breadcrumbs strong' })).toBeTruthy();
    expect(screen.getByRole('list', { name: 'Этапы регистрации сотрудника' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Персональная информация' })).toBeTruthy();
    expect(screen.getByText('Личные данные')).toBeTruthy();
    expect(screen.getByText('Занятость')).toBeTruthy();
    expect(screen.getByText('Образование')).toBeTruthy();
    expect(screen.getAllByText('Документы').length).toBeGreaterThan(0);
    expect(screen.queryByText('Заполнение карточки')).toBeNull();
    expect(screen.queryByText('Заполните этапы для добавления нового сотрудника в систему. Данные сохраняются автоматически.')).toBeNull();
    expect(screen.queryByText('Заполняется')).toBeNull();
    expect(screen.queryByText('Ожидает')).toBeNull();
    expect(screen.queryByLabelText('Департамент')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: /Продолжить/i }));
    expect(await screen.findByText('Укажите фамилию')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Персональная информация' })).toBeTruthy();

    expect(screen.getByRole('button', { name: /Продолжить/i })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /^Сохранить$/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /Очистить/i })).toBeNull();
  });

  it('opens planned HR modules for every persona in unified mode', async () => {
    useDeveloperStore.setState({ persona: 'secretary' });
    const view = renderRoute('/hr/calendar');
    expect(await screen.findByRole('heading', { name: 'Календарь' })).toBeTruthy();
    expect(screen.getByText('Ближайшие события')).toBeTruthy();

    view.unmount();
    useDeveloperStore.setState({ persona: 'employee' });
    renderRoute('/hr/terminations');
    expect(await screen.findByRole('heading', { name: 'Увольнения' })).toBeTruthy();
  });

  it('opens backend workforce workflows with role-specific creation actions', async () => {
    useDeveloperStore.setState({ persona: 'employee' });
    const leaveView = renderRoute('/hr/leave');
    expect(await screen.findByRole('heading', { name: 'Отпуска' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Создать заявку' })).toBeTruthy();

    leaveView.unmount();
    renderRoute('/hr/business-trips');
    expect(await screen.findByRole('heading', { name: 'Командировки' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Создать заявку' })).toBeTruthy();

    cleanup();
    useDeveloperStore.setState({ persona: 'hr-specialist' });
    renderRoute('/hr/terminations');
    expect(await screen.findByRole('heading', { name: 'Увольнения' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Начать увольнение' })).toBeTruthy();
  });

  it('opens backend hiring approvals as clickable records', async () => {
    useDeveloperStore.setState({ persona: 'hr-director' });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: [{
          id: 'request-1', requestNumber: 'HR-HIRE-2026-00002', candidateName: 'Смагулов Рамин Эрнарович',
          status: 'under_review', currentStageName: 'Директор HR-департамента', createdAt: '2026-07-16T10:00:00Z',
          employmentData: { department: 'HR', position: 'HR специалист' }
        }],
        meta: { requestId: 'test-request' }
      })
    }));

    renderRoute('/hr/approvals');

    expect(await screen.findByRole('heading', { name: 'Согласования' })).toBeTruthy();
    const requestLink = await screen.findByRole('link', { name: /HR-HIRE-2026-00002.*Смагулов Рамин Эрнарович/i });
    expect(requestLink.getAttribute('href')).toBe('/hiring/requests/request-1');
  });
});
