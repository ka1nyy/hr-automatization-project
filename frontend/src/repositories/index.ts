import { createApiRepositories } from './apiRepositories';
import { MockCorrespondenceRepository, MockOperationsRepository, MockOrganizationRepository, MockTaskRepository, MockWorkflowRepository } from './mockRepositories';

export const repositories = import.meta.env.MODE === 'test' ? {
  correspondence: new MockCorrespondenceRepository(),
  tasks: new MockTaskRepository(),
  workflows: new MockWorkflowRepository(),
  organization: new MockOrganizationRepository(),
  operations: new MockOperationsRepository()
} : createApiRepositories();
