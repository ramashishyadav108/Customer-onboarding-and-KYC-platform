import { expect, test } from '@playwright/test';
import { API, expectNoSeriousAxe, login } from './helpers';

// Runs only against a backend started with ADMIN_SIGNUP=open (LIVE_ADMIN_SIGNUP=open):
// an Admin sign-up is active at once, KYC analyst and compliance officer requests still wait (AC-14.11).
test.skip(process.env.LIVE_ADMIN_SIGNUP !== 'open', 'needs a backend running ADMIN_SIGNUP=open');
test.describe.configure({ mode: 'serial' });

const PASSWORD = 'synthetic-pass-123';

test('the sign-up page tells the truth: Admin needs no approval, analyst and officer do', async ({ page }) => {
  await page.goto('/signup');
  const type = page.getByLabel('I am a');
  await type.selectOption('admin');
  await expect(page.getByRole('note')).toContainText('Admin sign-up is open on this server');
  await expect(page.getByRole('button', { name: 'Create account' })).toBeVisible();
  await type.selectOption('kyc-analyst');
  await expect(page.getByRole('note')).toContainText('must be approved by an administrator');
  await expect(page.getByRole('button', { name: 'Request account' })).toBeVisible();
  await type.selectOption('compliance-officer');
  await expect(page.getByRole('button', { name: 'Request account' })).toBeVisible();
  await expectNoSeriousAxe(page);
});

test('an admin signs up and lands on the dashboard with no approval, and can manage users', async ({ page }) => {
  await page.goto('/signup');
  await page.getByLabel('I am a').selectOption('admin');
  await page.getByLabel('Username').fill('founder.admin');
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
  await page.getByLabel('Confirm password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('heading', { name: 'Operational reports' })).toBeVisible();
  await expect(page.getByText('Signed in as admin')).toBeVisible();
  await page.goto('/admin/users');
  await expect(page.getByRole('row', { name: /founder\.admin/ })).toContainText('Active');
});

test('the new admin can sign in again and approve a pending analyst and officer request', async ({ page, browser }) => {
  for (const [username, role] of [['analyst.req', 'kyc-analyst'], ['officer.req', 'compliance-officer']]) {
    const res = await fetch(`${API}/auth/signup`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ username, password: PASSWORD, role }) });
    expect(((await res.json()) as { status: string }).status).toBe('PENDING_APPROVAL');
    const attempt = await fetch(`${API}/auth/login`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ username, password: PASSWORD }) });
    expect(attempt.status).toBe(403);
  }
  await login(page, 'founder.admin', PASSWORD);
  await page.goto('/admin/users');
  await page.getByRole('button', { name: 'Approve analyst.req' }).click();
  await expect(page.getByText('analyst.req approved as KYC analyst.')).toBeVisible();
  await page.getByRole('button', { name: 'Approve officer.req' }).click();
  await expect(page.getByText('officer.req approved as Compliance officer.')).toBeVisible();

  const officer = await (await browser.newContext()).newPage();
  await login(officer, 'officer.req', PASSWORD);
  await expect(officer.getByRole('heading', { name: 'Manual review queue' })).toBeVisible();
});
