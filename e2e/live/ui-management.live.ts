import { expect, test, type Page } from '@playwright/test';
import { API, expectNoSeriousAxe, login, seedCase } from './helpers';

// Live-backend checks for admin user/role management (AC-11), checklist versions (AC-12), analyst
// queries (AC-13) and the four-role authorization boundary (NFR-04). Runs after ui-groups.live.ts
// (file order) because that suite expects an empty database first.
test.describe.configure({ mode: 'serial' });

const PASSWORD = 'synthetic-pass-123';
const STAFF_PAGES = ['/admin/users', '/admin/checklists', '/admin/dashboard', '/admin/rule-sets', '/admin/watchlist'];

async function asProspect(page: Page, c: { caseId: string; token: string }) {
  await page.goto('/portal/register');
  await page.evaluate(([t, id]) => sessionStorage.setItem('onboardx.session', JSON.stringify({ token: t, role: 'prospect', caseId: id })), [c.token, c.caseId]);
}

async function createUser(page: Page, username: string, roleLabel: string) {
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(PASSWORD);
  await page.getByLabel('Role', { exact: true }).selectOption({ label: roleLabel });
  await page.getByRole('button', { name: 'Create user' }).click();
  await expect(page.getByText(`User ${username} created.`)).toBeVisible();
}

test.describe('AC-11 users and roles (admin UI + real API)', () => {
  test('admin creates a user, who can then sign in; own row has no controls', async ({ page, browser }) => {
    await login(page, 'admin1');
    await page.goto('/admin/users');
    await expect(page.getByRole('heading', { name: 'Admin: users and roles' })).toBeVisible();
    await expect(page.getByLabel('Role for admin1')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Deactivate admin1' })).toHaveCount(0);
    await page.getByRole('button', { name: 'Create user' }).click();
    await expect(page.getByText('Choose a role.')).toBeVisible();
    await createUser(page, 'analyst.two', 'KYC analyst');
    await expect(page.getByRole('cell', { name: 'analyst.two', exact: true })).toBeVisible();

    const other = await browser.newPage();
    await other.goto('/login');
    await login(other, 'analyst.two', PASSWORD);
    await expect(other.getByRole('heading', { name: 'Analyst workbench' })).toBeVisible();
    await other.close();
  });

  test('duplicate usernames and weak passwords are rejected with messages', async ({ page }) => {
    await login(page, 'admin1');
    await page.goto('/admin/users');
    await page.getByLabel('Username').fill('analyst.two');
    await page.getByLabel('Password').fill(PASSWORD);
    await page.getByLabel('Role', { exact: true }).selectOption({ label: 'Admin' });
    await page.getByRole('button', { name: 'Create user' }).click();
    await expect(page.getByRole('alert')).toContainText(/already in use/i);
    await page.getByLabel('Password').fill('short');
    await page.getByRole('button', { name: 'Create user' }).click();
    await expect(page.getByText('Use 10 to 128 characters.')).toBeVisible();
  });

  test('deactivating a user kills the live session and blocks sign-in; reactivation restores it', async ({ page, browser }) => {
    const victim = await browser.newPage();
    await login(victim, 'analyst.two', PASSWORD);
    await expect(victim.getByRole('heading', { name: 'Analyst workbench' })).toBeVisible();

    await login(page, 'admin1');
    await page.goto('/admin/users');
    await page.getByRole('button', { name: 'Deactivate analyst.two' }).click();
    await expect(page.getByText('analyst.two deactivated.')).toBeVisible();

    await victim.getByLabel('State').selectOption('INITIATED'); // triggers an authenticated request
    await expect(victim).toHaveURL(/\/login/);
    await victim.getByLabel('Username').fill('analyst.two');
    await victim.getByLabel('Password').fill(PASSWORD);
    await victim.getByRole('button', { name: 'Sign in' }).click();
    await expect(victim.getByRole('alert')).toContainText(/invalid credentials/i);

    await page.getByRole('button', { name: 'Reactivate analyst.two' }).click();
    await expect(page.getByText('analyst.two reactivated.')).toBeVisible();
    await login(victim, 'analyst.two', PASSWORD);
    await expect(victim.getByRole('heading', { name: 'Analyst workbench' })).toBeVisible();
    await victim.close();
  });

  test('a role change takes effect on the next request of an already signed-in user', async ({ page, browser }) => {
    const staff = await browser.newPage();
    await login(staff, 'analyst.two', PASSWORD);
    await staff.goto('/staff/workbench');
    await expect(staff.getByRole('heading', { name: 'Analyst workbench' })).toBeVisible();

    await login(page, 'admin1');
    await page.goto('/admin/users');
    await page.getByLabel('Role for analyst.two').selectOption({ label: 'Compliance officer' });
    await expect(page.getByText('Role for analyst.two changed.')).toBeVisible();

    const token = await staff.evaluate(() => (JSON.parse(sessionStorage.getItem('onboardx.session') ?? '{}') as { token: string }).token);
    const probe = (path: string) => fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` } }).then((r) => r.status);
    expect(await probe('/review-queue')).toBe(200); // now an officer
    expect(await probe('/admin/users')).toBe(403);
    await staff.close();
  });

  test('axe: users page', async ({ page }) => {
    await login(page, 'admin1');
    await page.goto('/admin/users');
    await expect(page.getByRole('heading', { name: 'Admin: users and roles' })).toBeVisible();
    await expectNoSeriousAxe(page);
  });
});

test.describe('AC-12 checklist versions (admin UI + real API)', () => {
  test('admin publishes a new Savings version and new prospects get it; old cases keep theirs', async ({ page }) => {
    const oldCase = await seedCase({ name: 'Test Person Old', contact: '9999999801', product: 'Savings', submit: false });
    await login(page, 'admin1');
    await page.goto('/admin/checklists');
    await expect(page.getByRole('heading', { name: 'Savings checklist - version 1' })).toBeVisible();
    await expectNoSeriousAxe(page);

    await page.getByLabel('Mandatory Photograph for Savings').click();
    await page.getByRole('button', { name: 'Publish new Savings version' }).click();
    await expect(page.getByRole('alert')).toContainText(/photograph must be included and mandatory/);
    await page.getByLabel('Mandatory Photograph for Savings').click();

    const classes = page.getByLabel('Accepted classes for ID proof (Savings)');
    await classes.fill('PAN, PASSPORT');
    await page.getByRole('button', { name: 'Publish new Savings version' }).click();
    await expect(page.getByText(/Savings checklist version 2 published/)).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Savings checklist - version 2' })).toBeVisible();

    const fresh = await seedCase({ name: 'Test Person New', contact: '9999999802', product: 'Savings', submit: false });
    const read = (c: { caseId: string; token: string }) =>
      fetch(`${API}/cases/${c.caseId}`, { headers: { Authorization: `Bearer ${c.token}` } }).then((r) => r.json() as Promise<{ checklist_version: number; checklist_items: { item_code: string; accepted_classes: string[] }[] }>);
    const oldView = await read(oldCase);
    const newView = await read(fresh);
    expect(oldView.checklist_version).toBe(1);
    expect(newView.checklist_version).toBe(2);
    expect(newView.checklist_items.find((i) => i.item_code === 'ID_PROOF')?.accepted_classes).toEqual(['PAN', 'PASSPORT']);
    expect(oldView.checklist_items.find((i) => i.item_code === 'ID_PROOF')?.accepted_classes).toContain('AADHAAR');

    await asProspect(page, fresh);
    await page.goto('/portal/documents');
    await expect(page.getByTestId('item-ID_PROOF')).toContainText('PAN, PASSPORT');
  });
});

test.describe('AC-13 analyst queries (analyst UI -> prospect UI -> analyst UI)', () => {
  test('analyst raises, prospect replies, analyst closes', async ({ page, browser }) => {
    const c = await seedCase({ name: 'Test Person Query', contact: '9999999803', product: 'Savings', submit: false, docs: 'two' });
    await login(page, 'analyst1');
    await page.goto(`/staff/cases/${c.caseId}`);
    await expect(page.getByText('No queries on this case.')).toBeVisible();
    await page.getByRole('button', { name: 'Raise query' }).click();
    await expect(page.getByText('Enter a message.')).toBeVisible();
    await page.getByLabel('New query to the prospect').fill('Please upload a clearer photograph');
    await page.getByRole('button', { name: 'Raise query' }).click();
    await expect(page.getByText('Please upload a clearer photograph')).toBeVisible();

    const context = await browser.newContext();
    const prospect = await context.newPage();
    await asProspect(prospect, c);
    await prospect.goto('/portal/status');
    await expect(prospect.getByRole('heading', { name: 'Questions from our team' })).toBeVisible();
    await expect(prospect.getByText('Please upload a clearer photograph')).toBeVisible();
    await prospect.getByLabel('Reply to query').fill('Uploaded a new photograph just now');
    await prospect.getByRole('button', { name: 'Send reply' }).click();
    await expect(prospect.getByText(/Uploaded a new photograph just now/)).toBeVisible();
    await expectNoSeriousAxe(prospect);

    await page.reload();
    await expect(page.getByText(/Uploaded a new photograph just now/)).toBeVisible();
    await expect(page.getByTestId(/^query-/).getByText('Answered')).toBeVisible();
    await page.getByRole('button', { name: 'Close query' }).click();
    await expect(page.getByTestId(/^query-/).getByText('Closed')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Close query' })).toHaveCount(0);

    await prospect.reload();
    await expect(prospect.getByLabel('Reply to query')).toHaveCount(0);
    await context.close();
  });

  test('an admin sees queries read-only and cannot raise them', async ({ page }) => {
    const c = await seedCase({ name: 'Test Person Admin View', contact: '9999999804', product: 'Savings', submit: false });
    await login(page, 'admin1');
    await page.goto(`/staff/cases/${c.caseId}`);
    await expect(page.getByText('No queries on this case.')).toBeVisible();
    await expect(page.getByLabel('New query to the prospect')).toHaveCount(0);
  });
});

test.describe('NFR-04 authorization boundary through the UI', () => {
  for (const role of ['analyst1', 'officer1']) {
    test(`${role} is sent to the forbidden page on admin-only pages`, async ({ page }) => {
      await login(page, role);
      for (const path of ['/admin/users', '/admin/checklists']) {
        await page.goto(path);
        await expect(page.getByRole('heading', { name: '403 Forbidden' }), path).toBeVisible();
      }
    });
  }

  test('a prospect cannot open any staff or admin page', async ({ page }) => {
    const c = await seedCase({ name: 'Test Person Boundary', contact: '9999999805', product: 'Savings', submit: false });
    await asProspect(page, c);
    for (const path of [...STAFF_PAGES, '/staff/workbench', '/staff/review']) {
      await page.goto(path);
      await expect(page.getByRole('heading', { name: '403 Forbidden' }), path).toBeVisible();
    }
  });

  test('API: forged staff token for a non-existent user is rejected', async () => {
    const forged = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJub2JvZHkiLCJyb2xlIjoiYWRtaW4iLCJleHAiOjk5OTk5OTk5OTl9.invalid';
    const r = await fetch(`${API}/admin/users`, { headers: { Authorization: `Bearer ${forged}` } });
    expect(r.status).toBe(401);
  });

  test('API: prospect token cannot read another case or its queries', async () => {
    const a = await seedCase({ name: 'Test Person A', contact: '9999999806', product: 'Savings', submit: false });
    const b = await seedCase({ name: 'Test Person B', contact: '9999999807', product: 'Savings', submit: false });
    const r = await fetch(`${API}/cases/${b.caseId}/queries`, { headers: { Authorization: `Bearer ${a.token}` } });
    expect(r.status).toBe(403);
  });
});
