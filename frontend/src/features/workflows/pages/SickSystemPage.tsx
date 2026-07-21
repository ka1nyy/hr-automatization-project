import { HeartPulse } from 'lucide-react';
import { ProcessWorkspace } from '../ProcessWorkspace';
import { sickSystemConfig } from '../configs';

/**
 * Sick leave has no operational backend yet (unlike leave/termination which are
 * served by WorkforceProcessPage). The records tab therefore shows an honest empty
 * state so the screen still matches the other three workforce workspaces in shape.
 */
function SickRecordsPlaceholder() {
  return (
    <div className="hiring-empty">
      <span><HeartPulse size={28} /></span>
      <strong>Оперативный модуль в разработке</strong>
      <p>Регистрация листов и справок нетрудоспособности и расчёт пособия появятся здесь после подключения backend. Полный регламент процесса доступен на соседних вкладках.</p>
    </div>
  );
}

export default function SickSystemPage() {
  return <ProcessWorkspace config={sickSystemConfig} recordsLabel="Случаи" operational={<SickRecordsPlaceholder />} />;
}
