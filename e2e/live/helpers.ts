import AxeBuilder from '@axe-core/playwright';
import { expect, type Page } from '@playwright/test';

export const API = `http://127.0.0.1:${process.env.LIVE_BACKEND_PORT ?? 8010}/api/v1`;
export const pdf = (name: string) => ({ name, mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 synthetic') });

export async function login(page: Page, username: string) {
  await page.goto('/login');
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(`demo-${username}-pass`);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL((u) => !u.pathname.startsWith('/login'));
}

export async function expectNoSeriousAxe(page: Page) {
  const r = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  const bad = r.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
  expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function call(method: string, path: string, token: string | null, body?: unknown): Promise<Response> {
  return fetch(API + path, { method, headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(body ? { 'content-type': 'application/json' } : {}) }, body: body ? JSON.stringify(body) : undefined });
}

export async function staffToken(username: string): Promise<string> {
  const r = await call('POST', '/auth/login', null, { username, password: `demo-${username}-pass` });
  return ((await r.json()) as { access_token: string }).access_token;
}

export async function seedCase(opts: { name: string; contact: string; product: 'Savings' | 'Current' | 'NRE'; submit: boolean; docs?: 'all' | 'two' }) {
  const lead = (await (await call('POST', '/leads', null, { name: opts.name, contact: opts.contact, product: opts.product })).json()) as { case_id: string; access_token: string };
  const t = lead.access_token;
  await call('PUT', `/cases/${lead.case_id}/profile`, t, { date_of_birth: '1990-04-12', annual_income: 3000000, occupation_category: 'SELF_EMPLOYED', country_code: 'IN', state_code: 'MH' });
  if (opts.docs) {
    const items = [['ID_PROOF', 'pan_valid.pdf'], ['ADDRESS_PROOF', 'utility-bill_valid.pdf'], ['PHOTOGRAPH', 'photograph_valid.pdf']].slice(0, opts.docs === 'all' ? 3 : 2);
    for (const [item, name] of items) {
      const fd = new FormData();
      fd.append('checklist_item', item);
      fd.append('file', new Blob(['%PDF-1.4 synthetic'], { type: 'application/pdf' }), name);
      await fetch(`${API}/cases/${lead.case_id}/documents`, { method: 'POST', headers: { Authorization: `Bearer ${t}` }, body: fd });
    }
  }
  if (opts.submit) await call('POST', `/cases/${lead.case_id}/submit`, t);
  return { caseId: lead.case_id, token: t };
}
