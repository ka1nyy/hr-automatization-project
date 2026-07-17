import { describe, expect, it } from 'vitest';
import { isProbationActive } from './apiHrRepository';

describe('employee probation status', () => {
  it('activates an employee immediately when probation is absent', () => {
    expect(isProbationActive(null, '2026-07-17')).toBe(false);
  });

  it('keeps an employee on probation through the contractual end date', () => {
    expect(isProbationActive('2026-10-17', '2026-07-17')).toBe(true);
    expect(isProbationActive('2026-10-17', '2026-10-17')).toBe(true);
  });

  it('activates an employee after probation expires', () => {
    expect(isProbationActive('2026-10-17', '2026-10-18')).toBe(false);
  });
});
