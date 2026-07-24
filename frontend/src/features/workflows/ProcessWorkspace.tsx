import { useState, type ReactNode } from 'react';
import { PageHeader } from '../../shared/components';
import { SegmentTabs } from './components';
import { buildReferenceTabs, ProcessReferenceIntro, type ProcessSystemConfig } from './ProcessSystemPage';

/**
 * A single /hr endpoint that unites the live process management (the `operational`
 * node — backend records and the create form) with the regulation reference for the
 * same process. The first tab is the operational workspace; the rest transcribe the
 * regulation. Every workforce process (найм, увольнение, отпуск, больничный) renders
 * through this shell so the four screens share one structure.
 */
export function ProcessWorkspace({ operational, config, recordsLabel }: { operational: ReactNode; config: ProcessSystemConfig; recordsLabel: string }) {
  const [tab, setTab] = useState('records');
  const referenceTabs = buildReferenceTabs(config);
  const tabs = [{ id: 'records', label: recordsLabel }, ...referenceTabs.map(({ id, label, count }) => ({ id, label, count }))];
  const activeReference = referenceTabs.find((item) => item.id === tab);

  return (
    <>
      <PageHeader eyebrow={config.meta.eyebrow} title={config.meta.title} description={config.meta.description} />
      <SegmentTabs tabs={tabs} active={tab} onChange={setTab} />
      {tab === 'records' ? (
        operational
      ) : (
        <>
          <ProcessReferenceIntro config={config} />
          {activeReference?.render()}
        </>
      )}
    </>
  );
}
