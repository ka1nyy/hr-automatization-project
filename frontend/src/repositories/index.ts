import { MockCorrespondenceRepository, MockOperationsRepository, MockOrganizationRepository, MockTaskRepository, MockWorkflowRepository } from './mockRepositories';
import {
  CoreOrganizationRepository,
  CoreWorkflowRepository,
  PlaceholderCorrespondenceRepository,
  PlaceholderOperationsRepository
} from './placeholderRepositories';
import { WorkflowTaskRepository } from './workflowTaskRepository';

export const repositories = import.meta.env.MODE === 'test' ? {
  correspondence: new MockCorrespondenceRepository(),
  tasks: new MockTaskRepository(),
  workflows: new MockWorkflowRepository(),
  organization: new MockOrganizationRepository(),
  operations: new MockOperationsRepository()
} : {
  // Correspondence and the operations dashboard lost their backend when
  // business_processes was removed; placeholders keep the pages rendering until
  // the real modules land on the core API.
  correspondence: new PlaceholderCorrespondenceRepository(),
  tasks: new WorkflowTaskRepository(),
  workflows: new CoreWorkflowRepository(),
  organization: new CoreOrganizationRepository(),
  operations: new PlaceholderOperationsRepository()
};
