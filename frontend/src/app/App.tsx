import { lazy, Suspense, useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '../widgets/AppShell';
import { useDeveloperStore } from '../shared/store';
import { DepartmentProvider } from '../features/hr/context/DepartmentContext';

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
const HrPlannedPage = lazy(() => import('../features/hr/pages/HrPlannedPage'));
const HiringRequestsPage = lazy(() => import('../features/hr/pages/HiringRequestsPage'));
const HiringRequestDetailsPage = lazy(() => import('../features/hr/pages/HiringRequestDetailsPage'));
const WorkforceProcessPage = lazy(() => import('../features/hr/pages/WorkforceProcessPage'));
const WorkforceProcessDetailsPage = lazy(() => import('../features/hr/pages/WorkforceProcessDetailsPage'));
const WorkflowsOverviewPage = lazy(() => import('../features/workflows/pages/WorkflowsOverviewPage'));
const HierarchyPage = lazy(() => import('../features/workflows/pages/HierarchyPage'));
const HiringSystemPage = lazy(() => import('../features/workflows/pages/HiringSystemPage'));
const TerminationWorkspacePage = lazy(() => import('../features/workflows/pages/TerminationWorkspacePage'));
const LeaveWorkspacePage = lazy(() => import('../features/workflows/pages/LeaveWorkspacePage'));
const SickSystemPage = lazy(() => import('../features/workflows/pages/SickSystemPage'));

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
    <DepartmentProvider><Routes>
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
        <Route path="departments/hr/leave" element={<Navigate to="/hr/leave" replace />} />
        <Route path="departments/hr/hiring/add-employee" element={<Navigate to="/hr/employees?add=true" replace />} />
        <Route path="hr" element={<Suspense fallback={<LoadingState />}><HrOverviewPage /></Suspense>} />
        <Route path="hr/employees" element={<Suspense fallback={<LoadingState />}><HrEmployeesPage /></Suspense>} />
        <Route path="hr/employees/:employeeId" element={<Suspense fallback={<LoadingState />}><HrEmployeeProfilePage /></Suspense>} />
        <Route path="hr/leave" element={<Suspense fallback={<LoadingState />}><LeaveWorkspacePage /></Suspense>} />
        <Route path="hr/leave/:id" element={<Suspense fallback={<LoadingState />}><WorkforceProcessDetailsPage kind="leave" /></Suspense>} />
        <Route path="hr/business-trips" element={<Suspense fallback={<LoadingState />}><WorkforceProcessPage kind="trip" /></Suspense>} />
        <Route path="hr/business-trips/:id" element={<Suspense fallback={<LoadingState />}><WorkforceProcessDetailsPage kind="trip" /></Suspense>} />
        <Route path="hr/calendar" element={<Suspense fallback={<LoadingState />}><HrPlannedPage kind="calendar" /></Suspense>} />
        <Route path="hr/sick-leave" element={<Suspense fallback={<LoadingState />}><SickSystemPage /></Suspense>} />
        <Route path="hr/terminations" element={<Suspense fallback={<LoadingState />}><TerminationWorkspacePage /></Suspense>} />
        <Route path="hr/terminations/:id" element={<Suspense fallback={<LoadingState />}><WorkforceProcessDetailsPage kind="termination" /></Suspense>} />
        <Route path="hr/documents" element={<Suspense fallback={<LoadingState />}><HrPlannedPage kind="documents" /></Suspense>} />
        <Route path="hr/approvals" element={<Suspense fallback={<LoadingState />}><HiringRequestsPage /></Suspense>} />
        <Route path="hr/systems" element={<Suspense fallback={<LoadingState />}><WorkflowsOverviewPage /></Suspense>} />
        <Route path="hr/hierarchy" element={<Suspense fallback={<LoadingState />}><HierarchyPage /></Suspense>} />
        <Route path="hr/hiring" element={<Suspense fallback={<LoadingState />}><HiringSystemPage /></Suspense>} />
        <Route path="hr/hiring/add-employee" element={<Navigate to="/hr/employees?add=true" replace />} />
        <Route path="hiring/requests" element={<Suspense fallback={<LoadingState />}><HiringRequestsPage /></Suspense>} />
        <Route path="hiring/inbox" element={<Suspense fallback={<LoadingState />}><HiringRequestsPage /></Suspense>} />
        <Route path="hiring/received" element={<Suspense fallback={<LoadingState />}><HiringRequestsPage /></Suspense>} />
        <Route path="hiring/requests/:id" element={<Suspense fallback={<LoadingState />}><HiringRequestDetailsPage /></Suspense>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes></DepartmentProvider>
  );
}
