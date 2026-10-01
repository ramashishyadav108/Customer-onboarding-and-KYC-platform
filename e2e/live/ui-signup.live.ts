import { expect, test, type Page } from '@playwright/test';
import { API, expectNoSeriousAxe, login, pdf } from './helpers';

// Live journey for sign-up, sign-in and RBAC (AC-14): a customer signs up and applies, a different
// user (the compliance officer) signs in and decides, the customer signs back in and sees the result.
// Runs after ui-management.live.ts (file order).
test.describe.configure({ mode: 'serial' });

const PASSWORD = 'synthetic-pass-123';
const CUSTOMER = 'rahul.verma';

async function signUp(page: Page, username: string, password = PASSWORD) {
  await page.goto('/signup');
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByLabel('Confirm password').fill(password);
  await page.getByRole('button', { name: 'Create account' }).click();
}

async function signOut(page: Page) {
  await page.getByRole('button', { name: 'Sign out' }).click();
}

async function signInAs(page: Page, username: string, password = PASSWORD) {
  await login(page, username, password);
}

test('the sign-in page is shared by customers and staff and lists demo accounts in dev', async ({ page }) => {
  await page.goto('/login');
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Create an account' })).toBeVisible();
  const demo = page.getByRole('complementary', { name: 'Demo accounts' });
  await expect(demo).toContainText('officer1');
  await expectNoSeriousAxe(page);
  await page.goto('/signup');
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible();
  await expectNoSeriousAxe(page);
});

test('sign-up validates input and rejects taken staff usernames', async ({ page }) => {
  await page.goto('/signup');
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByLabel('Username')).toHaveAttribute('aria-invalid', 'true');
  await signUp(page, 'admin1');
  await expect(page.getByText('That username is already taken.')).toBeVisible();
  await page.getByLabel('Username').fill('someone.else');
  await page.getByLabel('Confirm password').fill('does-not-match');
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByText('The passwords do not match.')).toBeVisible();
});

test('a role in the sign-up request cannot create staff', async () => {
  const res = await fetch(`${API}/auth/signup`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username: 'sneaky.user', password: PASSWORD, role: 'admin' }),
  });
  expect(res.status).toBe(201);
  const body = (await res.json()) as { role: string; access_token: string };
  expect(body.role).toBe('prospect');
  const admin = await fetch(`${API}/admin/users`, { headers: { Authorization: `Bearer ${body.access_token}` } });
  expect(admin.status).toBe(403);
});

test('customer signs up, applies and reaches manual review', async ({ page }) => {
  await signUp(page, CUSTOMER);
  await expect(page.getByRole('heading', { name: 'Register your interest' })).toBeVisible();
  await page.getByLabel('Full name').fill('Test Person One'); // on the watchlist: routes to manual review
  await page.getByLabel('Contact (phone or email)').fill('9999999901');
  await page.getByLabel('Account type').selectOption('Savings');
  await page.getByRole('button', { name: 'Start application' }).click();

  await expect(page.getByRole('heading', { name: 'Your profile' })).toBeVisible();
  await page.getByLabel('Date of birth').fill('1990-04-12');
  await page.getByLabel('Annual income (INR)').fill('3000000');
  await page.getByLabel('Occupation').selectOption('SELF_EMPLOYED');
  await page.getByLabel('Country code').fill('IN');
  await page.getByLabel(/State code/).fill('MH');
  await page.getByRole('button', { name: 'Save and continue' }).click();

  await expect(page.getByRole('heading', { name: 'Upload your documents' })).toBeVisible();
  await page.getByLabel('Upload ID proof').setInputFiles(pdf('pan_valid.pdf'));
  await page.getByLabel('Upload Address proof').setInputFiles(pdf('utility-bill_valid.pdf'));
  await page.getByLabel('Upload Photograph').setInputFiles(pdf('photograph_valid.pdf'));
  await page.getByRole('button', { name: 'Submit documents' }).click();
  await expect(page.getByRole('heading', { name: 'Application status' })).toBeVisible();
  await expect(page.getByText(/additional review by our compliance team/)).toBeVisible();
});

test('the customer signs back in and resumes the same application; registration is closed to them', async ({ page }) => {
  await signInAs(page, CUSTOMER);
  await expect(page.getByRole('heading', { name: 'Application status' })).toBeVisible();
  await expect(page.getByText(/additional review by our compliance team/)).toBeVisible();
  await page.goto('/portal/register');
  await expect(page.getByRole('heading', { name: 'Application status' })).toBeVisible(); // redirected
  await signOut(page);
  await expect(page).toHaveURL(/\/login/);
});

test('RBAC: the customer account is blocked from every staff and admin page', async ({ page }) => {
  await signInAs(page, CUSTOMER);
  await expect(page.getByRole('heading', { name: 'Application status' })).toBeVisible();
  for (const path of ['/staff/review', '/staff/workbench', '/admin/dashboard', '/admin/users', '/admin/checklists']) {
    await page.goto(path);
    await expect(page.getByRole('heading', { name: '403 Forbidden' }), path).toBeVisible();
  }
});

test('RBAC: the compliance officer signs in on the shared page, sees the case and decides it', async ({ page }) => {
  await signInAs(page, 'officer1', 'demo-officer1-pass');
  await expect(page.getByRole('heading', { name: 'Manual review queue' })).toBeVisible();
  await expect(page.getByRole('button', { name: /^Review / })).toHaveCount(1);
  await page.getByRole('button', { name: /^Review / }).click();
  await page.getByLabel('Reason code').selectOption('FALSE_POSITIVE_CLEARED');
  await page.getByRole('button', { name: 'Approve case' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Confirm decision' }).click();
  await expect(page.getByText(/approved with reason FALSE_POSITIVE_CLEARED/)).toBeVisible();
  await expect(page.getByText('No cases are waiting for manual review.')).toBeVisible();
  // the officer cannot use the customer or admin areas
  await page.goto('/admin/users');
  await expect(page.getByRole('heading', { name: '403 Forbidden' })).toBeVisible();
});

test('the customer sees the officer decision and the new account after signing in again', async ({ page }) => {
  await signInAs(page, CUSTOMER);
  await expect(page.getByRole('heading', { name: 'Application status' })).toBeVisible();
  await expect(page.getByText(/Your account is open: /)).toBeVisible();
});

test('the admin sees the customer account and cannot change a prospect', async ({ page }) => {
  await signInAs(page, 'admin1', 'demo-admin1-pass');
  await page.goto('/admin/users');
  const row = page.getByRole('row', { name: new RegExp(CUSTOMER) });
  await expect(row).toContainText('Prospect');
  await expect(row.getByRole('button')).toHaveCount(0);
});

test('deactivating the customer account ends their session and sign-in', async ({ page, browser }) => {
  const context = await browser.newContext();
  const customer = await context.newPage();
  await signInAs(customer, CUSTOMER);
  await expect(customer.getByRole('heading', { name: 'Application status' })).toBeVisible();

  const token = await (await fetch(`${API}/auth/login`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ username: 'admin1', password: 'demo-admin1-pass' }) })).json() as { access_token: string };
  const users = (await (await fetch(`${API}/admin/users`, { headers: { Authorization: `Bearer ${token.access_token}` } })).json()) as { items: { user_id: string; username: string }[] };
  const uid = users.items.find((u) => u.username === CUSTOMER)!.user_id;
  const off = await fetch(`${API}/admin/users/${uid}/deactivate`, { method: 'POST', headers: { Authorization: `Bearer ${token.access_token}` } });
  expect(off.status).toBe(200);

  await customer.getByRole('button', { name: 'Refresh status' }).click();
  await expect(customer).toHaveURL(/\/login/);
  await customer.getByLabel('Username').fill(CUSTOMER);
  await customer.getByLabel('Password').fill(PASSWORD);
  await customer.getByRole('button', { name: 'Sign in' }).click();
  await expect(customer.getByRole('alert')).toContainText(/invalid credentials/i);
  await context.close();
  void page;
});
