import { ApiHrRepository } from './apiHrRepository';
import { MockHrRepository } from './mockHrRepository';

export const hrRepository = import.meta.env.MODE === 'test' ? new MockHrRepository() : new ApiHrRepository();
