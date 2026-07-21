import { ProcessWorkspace } from '../ProcessWorkspace';
import HiringRequestsPage from '../../hr/pages/HiringRequestsPage';
import { hiringSystemConfig } from '../configs';

export default function HiringSystemPage() {
  return <ProcessWorkspace config={hiringSystemConfig} recordsLabel="Заявки" operational={<HiringRequestsPage embedded />} />;
}
