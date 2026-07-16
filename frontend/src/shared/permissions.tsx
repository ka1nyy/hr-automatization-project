import type { PropsWithChildren } from 'react';
import { useDeveloperStore } from './store';
import type { PersonaId } from './types';

export type Permission =
  | 'correspondence.read' | 'correspondence.create' | 'correspondence.register' | 'correspondence.resolve'
  | 'task.read' | 'task.claim' | 'task.complete' | 'workflow.read' | 'workflow.definition.edit'
  | 'organization.read' | 'audit.read' | 'analytics.read' | 'admin.manage'
  | 'hr.read' | 'hr.employees.read' | 'hr.sensitive.read' | 'hr.leave.create' | 'hr.leave.review' | 'hr.messages.read'
  | 'hiring.initiate' | 'hiring.approve' | 'hiring.receive' | 'hiring.monitor';

const matrix: Record<PersonaId, Permission[]> = {
  secretary: ['correspondence.read', 'correspondence.create', 'correspondence.register', 'task.read', 'task.claim', 'task.complete', 'workflow.read', 'organization.read', 'audit.read'],
  executive: ['correspondence.read', 'correspondence.resolve', 'task.read', 'task.claim', 'task.complete', 'workflow.read', 'organization.read', 'audit.read', 'analytics.read'],
  employee: ['correspondence.read', 'correspondence.create', 'task.read', 'task.claim', 'task.complete', 'workflow.read', 'organization.read', 'hr.read', 'hr.leave.create'],
  'hr-specialist': ['correspondence.read', 'task.read', 'task.claim', 'task.complete', 'workflow.read', 'organization.read', 'audit.read', 'hr.read', 'hr.employees.read', 'hr.sensitive.read', 'hr.leave.create', 'hr.leave.review', 'hr.messages.read', 'hiring.initiate'],
  'process-designer': ['correspondence.read', 'task.read', 'workflow.read', 'workflow.definition.edit', 'organization.read', 'audit.read', 'analytics.read', 'admin.manage', 'hiring.monitor'],
  'hr-initiator': ['organization.read', 'audit.read', 'hr.read', 'hr.employees.read', 'hr.sensitive.read', 'hiring.initiate'],
  'hr-director': ['organization.read', 'audit.read', 'hr.read', 'hiring.approve'],
  'economic-director': ['organization.read', 'audit.read', 'hiring.approve'],
  'commission-reviewer': ['organization.read', 'audit.read', 'hiring.approve'],
  'legal-reviewer': ['organization.read', 'audit.read', 'hiring.approve'],
  'board-chairman': ['organization.read', 'audit.read', 'hiring.approve'],
  accountant: ['organization.read', 'hiring.receive'],
  'it-specialist': ['organization.read', 'hiring.receive']
};

export function usePermission(permission: Permission) {
  const persona = useDeveloperStore((state) => state.persona);
  return matrix[persona].includes(permission);
}

export function PermissionGate({ permission, children, fallback = null }: PropsWithChildren<{ permission: Permission; fallback?: React.ReactNode }>) {
  return usePermission(permission) ? children : fallback;
}

export function getPermissions(persona: PersonaId) { return matrix[persona]; }
