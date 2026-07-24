import { ProcessWorkspace } from '../ProcessWorkspace';
import WorkforceProcessPage from '../../hr/pages/WorkforceProcessPage';
import { leaveSystemConfig } from '../configs';

export default function LeaveWorkspacePage() {
  return <ProcessWorkspace config={leaveSystemConfig} recordsLabel="Заявки" operational={<WorkforceProcessPage kind="leave" embedded />} />;
}
