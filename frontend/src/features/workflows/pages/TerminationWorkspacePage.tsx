import { ProcessWorkspace } from '../ProcessWorkspace';
import WorkforceProcessPage from '../../hr/pages/WorkforceProcessPage';
import { terminationSystemConfig } from '../configs';

export default function TerminationWorkspacePage() {
  return <ProcessWorkspace config={terminationSystemConfig} recordsLabel="Дела" operational={<WorkforceProcessPage kind="termination" embedded />} />;
}
