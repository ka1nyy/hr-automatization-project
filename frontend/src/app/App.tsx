import { lazy, Suspense, useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '../widgets/AppShell';
import { useDeveloperStore } from '../shared/store';

const DashboardPage = lazy(() => import('../features/dashboard/DashboardPage'));
const IncomingPage = lazy(() => import('../features/correspondence/IncomingPage'));
const RegisterIncomingPage = lazy(() => import('../features/correspondence/RegisterIncomingPage'));
const CorrespondenceDetailPage = lazy(() => import('../features/correspondence/CorrespondenceDetailPage'));
const TasksPage = lazy(() => import('../features/tasks/TasksPage'));
const ProcessesPage = lazy(() => import('../features/processes/ProcessesPage'));
const OrganizationPage = lazy(() => import('../features/organization/OrganizationPage'));
const HrOverviewPage = lazy(() => import('../features/hr/pages/HrOverviewPage'));
const HrEmployeesPage = lazy(() => import('../features/hr/pages/HrEmployeesPage'));
const HrEmployeeProfilePage = lazy(() => import('../features/hr/pages/HrEmployeeProfilePage'));
const HrLeavePage = lazy(() => import('../features/hr/pages/HrLeavePage'));

function LoadingState() {
  return <div className="page-loading" aria-label="Загрузка"><span /><span /><span /></div>;
}

export function App() {
  const theme = useDeveloperStore((state) => state.theme);
  useEffect(() => {
    const resolved = theme === 'system' ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : theme;
    document.documentElement.dataset.theme = resolved;
  }, [theme]);

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Suspense fallback={<LoadingState />}><DashboardPage /></Suspense>} />
        <Route path="correspondence/incoming" element={<Suspense fallback={<LoadingState />}><IncomingPage /></Suspense>} />
        <Route path="correspondence/incoming/new" element={<Suspense fallback={<LoadingState />}><RegisterIncomingPage /></Suspense>} />
        <Route path="correspondence/incoming/:id" element={<Suspense fallback={<LoadingState />}><CorrespondenceDetailPage /></Suspense>} />
        <Route path="tasks" element={<Suspense fallback={<LoadingState />}><TasksPage /></Suspense>} />
        <Route path="processes" element={<Suspense fallback={<LoadingState />}><ProcessesPage /></Suspense>} />
        <Route path="organization" element={<Suspense fallback={<LoadingState />}><OrganizationPage /></Suspense>} />
        <Route path="departments/hr" element={<Suspense fallback={<LoadingState />}><HrOverviewPage /></Suspense>} />
        <Route path="departments/hr/employees" element={<Suspense fallback={<LoadingState />}><HrEmployeesPage /></Suspense>} />
        <Route path="departments/hr/employees/:employeeId" element={<Suspense fallback={<LoadingState />}><HrEmployeeProfilePage /></Suspense>} />
        <Route path="departments/hr/leave" element={<Suspense fallback={<LoadingState />}><HrLeavePage /></Suspense>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
