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
  });

  afterEach(cleanup);

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
    expect(await screen.findByRole('heading', { name: 'Процессы HR' })).toBeTruthy();
    expect((await screen.findAllByText('Согласование отпуска')).length).toBeGreaterThan(0);
    expect(screen.queryByText('Обработка входящей корреспонденции')).toBeNull();
  });

  it('keeps the employee in self-service and out of the HR directory', async () => {
    useDeveloperStore.setState({ persona: 'employee' });
    const view = renderRoute('/departments/hr/leave');
    expect(await screen.findByRole('heading', { name: 'Мои отпуска' })).toBeTruthy();

    view.unmount();
    renderRoute('/departments/hr/employees');
    expect(await screen.findByRole('heading', { name: 'Доступ ограничен' })).toBeTruthy();
  });

  it('shows dynamic HR context and stores Add Employee drafts locally', async () => {
    useDeveloperStore.setState({ persona: 'hr-specialist' });
    renderRoute('/hr/hiring/add-employee');

    expect(await screen.findByRole('heading', { name: 'Служебная записка на приём' })).toBeTruthy();
    expect(screen.getByText('Добавить сотрудника', { selector: '.breadcrumbs strong' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Сохранить черновик/i }));
    expect(localStorage.getItem('ertis.hr.add-employee.draft.v1')).toContain('Зарина Ахметова');
    expect(screen.getByText(/Файлы не сохраняются/i)).toBeTruthy();
  });
});
