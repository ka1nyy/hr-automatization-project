import type { AddEmployeeFormValues } from './schema';

export type SubmissionResult = { id: string; submittedAt: string };

/** Future integration boundary. It is intentionally not implemented or invoked in this release. */
export interface AddEmployeeSubmissionRepository {
  submit(values: AddEmployeeFormValues): Promise<SubmissionResult>;
}
