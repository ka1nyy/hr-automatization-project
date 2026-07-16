import type { WorkTask } from '../shared/types';
import { ApiClient } from './apiRepositories';
import type { TaskRepository } from './contracts';

type WorkflowTaskDto = {
  id: string;
  status: string;
  dueAt: string | null;
  createdAt: string;
  revision: number;
  stepCode: string;
  stepName: string;
  allowedActions: string[];
  businessType: string;
  businessEntityId: string;
  organizationId: string;
};

const businessTypeLabels: Record<string, string> = {
  recruitmentRequest: 'Заявка на подбор',
  hiringCase: 'Найм',
  terminationCase: 'Увольнение'
};

// The generic engine accepts several verbs; pick the most affirmative one the
// step allows when the user presses the single "complete" button.
const ACTION_PRIORITY = ['complete', 'approve', 'submit'] as const;

function toWorkTask(dto: WorkflowTaskDto): WorkTask {
  const open = dto.status === 'pending' || dto.status === 'active';
  return {
    id: dto.id,
    title: dto.stepName,
    documentNumber: dto.businessEntityId.slice(0, 8).toUpperCase(),
    process: businessTypeLabels[dto.businessType] ?? dto.businessType,
    role: dto.stepCode,
    department: '—',
    dueDate: (dto.dueAt ?? dto.createdAt).slice(0, 10),
    priority: 'normal',
    state: open ? 'claimed' : 'completed',
    assignee: 'Вы'
  };
}

/** Serves the tasks page from the module-2 workflow engine. */
export class WorkflowTaskRepository implements TaskRepository {
  private tasks = new Map<string, WorkflowTaskDto>();

  constructor(private readonly api = new ApiClient()) {}

  async list(): Promise<WorkTask[]> {
    const items = await this.api.get<WorkflowTaskDto[]>('/workflow/tasks/my?pageSize=100');
    this.tasks = new Map(items.map((item) => [item.id, item]));
    return items.map(toWorkTask);
  }

  async claim(): Promise<WorkTask> {
    throw new Error('Задачи workflow назначаются исполнителям автоматически.');
  }

  async complete(id: string): Promise<WorkTask> {
    let task = this.tasks.get(id);
    if (!task) {
      await this.list();
      task = this.tasks.get(id);
    }
    if (!task) throw new Error('Задача не найдена.');
    const action = ACTION_PRIORITY.find((item) => task.allowedActions.includes(item)) ?? task.allowedActions[0];
    if (!action) throw new Error('У задачи нет доступных действий.');
    await this.api.post(`/workflow/tasks/${id}/actions`, {
      organizationId: task.organizationId,
      revision: task.revision,
      action,
      idempotencyKey: crypto.randomUUID()
    });
    return { ...toWorkTask(task), state: 'completed' };
  }
}
