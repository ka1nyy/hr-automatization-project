/**
 * Typed reference model for the four HR governance systems described in the
 * АО «СПК «Ертіс» internal regulations (Regламент найма, увольнения, отпусков и
 * рабочая модель иерархии). The regulations are approval drafts, so the frontend
 * treats them as an authoritative reference catalogue rather than live backend
 * data — every value here is transcribed from the source documents.
 */

export type StageOwner = string;

export interface WorkflowStage {
  index: number;
  title: string;
  owner: StageOwner;
  outcome: string;
  sla: string;
  /** Groups the stage into a lifecycle phase for the timeline rail. */
  phase: string;
}

export interface RoleDuty {
  role: string;
  responsibility: string;
  restriction: string;
}

export interface DecisionGate {
  code: string;
  question: string;
  action: string;
}

export interface RegistryDocument {
  code: string;
  title: string;
  preparedBy: string;
  signedBy: string;
}

export interface StatusState {
  code: string;
  meaning: string;
  owner: string;
  guard: string;
}

/** A row in a role × permission access matrix. */
export interface AccessRow {
  role: string;
  scope: string;
  sees: string;
  hidden: string;
}
