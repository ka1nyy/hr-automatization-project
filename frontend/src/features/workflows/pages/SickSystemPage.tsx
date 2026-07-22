import { useQueryClient } from '@tanstack/react-query';
import { HeartPulse, RefreshCw } from 'lucide-react';
import { ProcessMetrics } from '../../../shared/components';
import { ProcessWorkspace } from '../ProcessWorkspace';
import { sickSystemConfig } from '../configs';

/**
 * Sick leave has no operational backend yet (unlike leave/termination which are
 * served by WorkforceProcessPage). The records tab still shows the same
 * «Всего записей / Требуют действия / Завершено» strip as the other workforce
 * workspaces — the counters are simply zero until the backend is connected.
 */
function SickRecords() {
  const client = useQueryClient();
  return <>
    <ProcessMetrics icon={HeartPulse} total={0} actionable={0} completed={0} />
    <div className="hiring-list-toolbar">
      <span><HeartPulse size={17} />0 записей для вашей роли</span>
      <button className="secondary-button" onClick={() => void client.invalidateQueries()}><RefreshCw size={15} />Обновить</button>
    </div>
    <div className="hiring-empty">
      <span><HeartPulse size={28} /></span>
      <strong>Оперативный модуль в разработке</strong>
      <p>Регистрация листов и справок нетрудоспособности и расчёт пособия появятся здесь после подключения backend. Полный регламент процесса доступен на соседних вкладках.</p>
    </div>
  </>;
}

export default function SickSystemPage() {
  return <ProcessWorkspace config={sickSystemConfig} recordsLabel="Случаи" operational={<SickRecords />} />;
}
