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

    expect(await screen.findByRole('heading', { name: 'Каталог сотрудников' }, { timeout: 5000 })).toBeTruthy();
    expect(screen.getByText('Зарина Ахметова')).toBeTruthy();
  });

  it('keeps the employee in self-service and out of the HR directory', async () => {
    useDeveloperStore.setState({ persona: 'employee' });
    const view = renderRoute('/departments/hr/leave');
    expect(await screen.findByRole('heading', { name: 'Мои отпуска' })).toBeTruthy();

    view.unmount();
    renderRoute('/departments/hr/employees');
    expect(await screen.findByRole('heading', { name: 'Доступ ограничен' })).toBeTruthy();
  });
});
