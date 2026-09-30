import { describe, expect, it } from 'vitest';
import { validateLead, validateProfile, validateReasonSelected, validateRuleSetDraft, validateUploadFile } from '@/lib/validation';
import { formatAge, formatBp, formatDateTime, formatDuration, humanize } from '@/lib/format';

const goodProfile = { date_of_birth: '1990-04-12', annual_income: '3000000', occupation_category: 'SELF_EMPLOYED', country_code: 'IN', state_code: 'MH' };

describe('lead validation', () => {
  it('AC-01: accepts a name, 10-digit phone and product', () => {
    expect(validateLead({ name: 'Meera Nair', contact: '9876543221', product: 'Savings' })).toEqual({});
  });
  it('AC-01: accepts an email contact', () => {
    expect(validateLead({ name: 'Meera Nair', contact: 'meera.nair@example.com', product: 'NRE' })).toEqual({});
  });
  it('AC-01: rejects empty fields with one message per field', () => {
    expect(Object.keys(validateLead({ name: ' ', contact: '', product: '' })).sort()).toEqual(['contact', 'name', 'product']);
  });
  it('AC-01: rejects a 9-digit phone and a name over 100 characters', () => {
    const e = validateLead({ name: 'a'.repeat(101), contact: '987654321', product: 'Current' });
    expect(e.contact).toMatch(/10-digit/);
    expect(e.name).toMatch(/100/);
  });
  it('AC-01: rejects a product outside Savings, Current and NRE', () => {
    expect(validateLead({ name: 'Meera', contact: '9876543221', product: 'Gold' }).product).toBeDefined();
  });
});

describe('profile validation', () => {
  it('AC-06: accepts a complete Indian profile', () => {
    expect(validateProfile(goodProfile, new Date('2026-10-01'))).toEqual({});
  });
  it('AC-06: requires state_code when country_code is IN', () => {
    expect(validateProfile({ ...goodProfile, state_code: '' }).state_code).toBeDefined();
  });
  it('AC-06: does not require state_code for a foreign country', () => {
    expect(validateProfile({ ...goodProfile, country_code: 'GB', state_code: '' })).toEqual({});
  });
  it('AC-06: rejects decimal income, lowercase country and a future birth date', () => {
    const e = validateProfile({ ...goodProfile, annual_income: '30000.50', country_code: 'in', date_of_birth: '2030-01-01' }, new Date('2026-10-01'));
    expect(e.annual_income).toBeDefined();
    expect(e.country_code).toBeDefined();
    expect(e.date_of_birth).toMatch(/future/);
  });
  it('AC-06: rejects missing date of birth and occupation', () => {
    const e = validateProfile({ ...goodProfile, date_of_birth: '', occupation_category: '' });
    expect(e.date_of_birth).toBeDefined();
    expect(e.occupation_category).toBeDefined();
  });
});

describe('upload and reason validation', () => {
  it('AC-02: accepts pdf, jpg and png under 5 MB', () => {
    expect(validateUploadFile({ name: 'pan_valid.pdf', size: 1000 })).toBeNull();
    expect(validateUploadFile({ name: 'PHOTO.PNG', size: 5 * 1024 * 1024 })).toBeNull();
  });
  it('AC-02: rejects exe, oversize and empty files', () => {
    expect(validateUploadFile({ name: 'bad_type.exe', size: 10 })).toMatch(/PDF/);
    expect(validateUploadFile({ name: 'big.pdf', size: 5 * 1024 * 1024 + 1 })).toMatch(/5 MB/);
    expect(validateUploadFile({ name: 'empty.pdf', size: 0 })).toMatch(/empty/);
  });
  it('AC-08: requires a reason code selection', () => {
    expect(validateReasonSelected('')).not.toBeNull();
    expect(validateReasonSelected('RISK_ACCEPTED')).toBeNull();
  });
});

describe('rule set draft validation', () => {
  const w = { age: '20', income_band: '25', occupation_category: '30', geography: '25' };
  it('AC-06: accepts weights summing to 100 and ordered thresholds', () => {
    expect(validateRuleSetDraft(w, '29', '59')).toEqual({});
  });
  it('AC-06: rejects weights not summing to 100', () => {
    expect(validateRuleSetDraft({ ...w, age: '30' }, '29', '59').weights).toMatch(/110/);
  });
  it('AC-06: rejects non-integer weights and unordered thresholds (NFR-01)', () => {
    expect(validateRuleSetDraft({ ...w, age: '20.5' }, '29', '59').age).toBeDefined();
    expect(validateRuleSetDraft(w, '60', '59').thresholds).toBeDefined();
    expect(validateRuleSetDraft(w, 'x', '59').low_max).toBeDefined();
  });
});

describe('formatting (integers only)', () => {
  it('AC-10: formats basis points without floats', () => {
    expect(formatBp(6000)).toBe('60.00%');
    expect(formatBp(5725)).toBe('57.25%');
    expect(formatBp(5)).toBe('0.05%');
  });
  it('AC-10: formats durations and ages', () => {
    expect(formatDuration(45)).toBe('45 s');
    expect(formatDuration(125)).toBe('2 min 5 s');
    expect(formatDuration(3720)).toBe('1 h 2 min');
    expect(formatAge(30)).toBe('30 min');
    expect(formatAge(125)).toBe('2 h 5 min');
    expect(formatAge(1500)).toBe('1 d 1 h');
  });
  it('AC-09: formats timestamps in UTC and humanizes codes', () => {
    expect(formatDateTime('2026-10-01T09:30:00Z')).toBe('2026-10-01 09:30 UTC');
    expect(formatDateTime('nonsense')).toBe('nonsense');
    expect(humanize('MANUAL_REVIEW')).toBe('Manual review');
  });
});
