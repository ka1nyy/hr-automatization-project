import { hrRepository } from '../features/hr/api';
import type { Correspondence, DashboardSnapshot, Employee, ProcessDefinition, WorkTask } from '../shared/types';
import { ApiClient } from './apiRepositories';
import type {
  CorrespondenceRepository,
  OperationsRepository,
  OrganizationRepository,
  TaskRepository,
  WorkflowRepository
} from './contracts';

/**
 * The demo business_processes backend module was removed; these sections wait
 * for their real implementation on the core API. Reads return empty data so
 * the pages render honest empty states, writes fail with a clear message.
 */
const RETIRED_MESSAGE = 'Раздел ожидает реализации на новом бэкенде.';

const retired = () => new Error(RETIRED_MESSAGE);

export class PlaceholderCorrespondenceRepository implements CorrespondenceRepository {
  async listIncoming(): Promise<Correspondence[]> { return []; }
  async getIncoming(): Promise<Correspondence> { throw retired(); }
  async checkDuplicate(): Promise<Correspondence | null> { return null; }
  async registerIncoming(): Promise<Correspondence> { throw retired(); }
  async sendForResolution(): Promise<Correspondence> { throw retired(); }
}

export class PlaceholderTaskRepository implements TaskRepository {
  async list(): Promise<WorkTask[]> { return []; }
  async claim(): Promise<WorkTask> { throw retired(); }
  async complete(): Promise<WorkTask> { throw retired(); }
}

export class PlaceholderWorkflowRepository implements WorkflowRepository {
  async listDefinitions(): Promise<ProcessDefinition[]> { return []; }
  async retryIncident(): Promise<ProcessDefinition> { throw retired(); }
}

type CoreProcessDefinition = {
  id: string;
  code: string;
  name: string;
  owner: string;
  versionNumber: number;
  state: ProcessDefinition['state'];
  steps: string[];
  activeInstances: number;
  updatedAt: string | null;
};

type ActiveStructure = { version: { organizationId: string } | null };

/** Process definitions are served by the core workflow API. */
export class CoreWorkflowRepository implements WorkflowRepository {
  constructor(private readonly api = new ApiClient()) {}

  /**
   * The workflow API scopes definitions by an explicit organization, unlike the
   * employee endpoints which resolve it from the principal. The active structure is
   * the only read that exposes the caller's organization id.
   */
  private async organizationId(): Promise<string> {
    const structure = await this.api.get<ActiveStructure>('/organization/structure/active');
    const id = structure.version?.organizationId;
    if (!id) throw new Error('Не удалось определить организацию текущего пользователя.');
    return id;
  }

  async listDefinitions(): Promise<ProcessDefinition[]> {
    const organizationId = await this.organizationId();
    const definitions = await this.api.get<CoreProcessDefinition[]>(
      `/workflow/definitions?organizationId=${encodeURIComponent(organizationId)}`
    );
    return definitions.map((item) => ({
      id: item.id,
      name: item.name,
      version: item.versionNumber,
      state: item.state,
      activeInstances: item.activeInstances,
      owner: item.owner,
      updatedAt: item.updatedAt ?? '',
      steps: item.steps
    }));
  }

  /** Instance recovery has no core endpoint yet; the catalogue is read-only. */
  async retryIncident(): Promise<ProcessDefinition> { throw retired(); }
}

export class PlaceholderOperationsRepository implements OperationsRepository {
  async dashboard(): Promise<DashboardSnapshot> {
    return {
      incomingToday: 0,
      awaitingResolution: 0,
      activeTasks: 0,
      overdue: 0,
      signatureQueue: 0,
      dispatchQueue: 0
    };
  }

  async reset() { /* Nothing to reset without a backing module. */ }
}

/** The employee directory is served by the core employees API. */
export class CoreOrganizationRepository implements OrganizationRepository {
  async listEmployees(): Promise<Employee[]> {
    const employees = await hrRepository.listEmployees();
    return employees.map((employee) => ({
      id: employee.id,
      name: employee.fullName,
      initials: employee.initials,
      role: employee.position,
      department: employee.department,
      candidateGroups: [],
      status: 'active'
    }));
  }
}
