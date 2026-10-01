import { expect, test } from '@playwright/test';
import { expectNoSeriousAxe, login, pdf } from './helpers';

// Runs only against a backend started with REVIEW_POLICY=manual (LIVE_REVIEW_POLICY=manual):
// every application, even a clean LOW-risk one, waits for a compliance officer (AC-15).
test.skip(process.env.LIVE_REVIEW_POLICY !== 'manual', 'needs a backend running REVIEW_POLICY=manual');
test.describe.configure({ mode: 'serial' });

const PASSWORD = 'synthetic-pass-123';
const CUSTOMER = 'anita.rao';

test('a clean customer application waits for the compliance officer instead of being auto-approved', async ({ page }) => {
  await page.goto('/signup');
  await page.getByLabel('Username').fill(CUSTOMER);
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
  await page.getByLabel('Confirm password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Create account' }).click();
  await page.getByLabel('Full name').fill('Test Person Alpha'); // clean: LOW risk, not on any watchlist
  await page.getByLabel('Contact (phone or email)').fill('9999999921');
  await page.getByLabel('Account type').selectOption('Savings');
  await page.getByRole('button', { name: 'Start application' }).click();
  await page.getByLabel('Date of birth').fill('1990-04-12');
  await page.getByLabel('Annual income (INR)').fill('3000000');
  await page.getByLabel('Occupation').selectOption('SALARIED');
  await page.getByLabel('Country code').fill('IN');
  await page.getByLabel(/State code/).fill('MH');
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await page.getByLabel('Upload ID proof').setInputFiles(pdf('pan_valid.pdf'));
  await page.getByLabel('Upload Address proof').setInputFiles(pdf('utility-bill_valid.pdf'));
  await page.getByLabel('Upload Photograph').setInputFiles(pdf('photograph_valid.pdf'));
  await page.getByRole('button', { name: 'Submit documents' }).click();

  await expect(page.getByRole('heading', { name: 'Application status' })).toBeVisible();
  await expect(page.getByText(/additional review by our compliance team/)).toBeVisible();
  await expect(page.getByText(/Your account is open/)).toHaveCount(0);
  const progress = page.getByRole('list', { name: 'Application progress' });
  await expect(progress).toContainText('Screening complete'); // rule-based screening still ran
  await expect(progress.locator('[aria-current="step"]')).toContainText('Under manual review');
});

test('the compliance officer sees the policy reason and approves; the customer then has an account', async ({ page, browser }) => {
  await login(page, 'officer1', 'demo-officer1-pass');
  await expect(page.getByRole('heading', { name: 'Manual review queue' })).toBeVisible();
  await expect(page.getByText(/MANUAL_POLICY - Bank policy/)).toBeVisible();
  await page.getByRole('button', { name: /^Review / }).click();
  await expectNoSeriousAxe(page);
  await page.getByLabel('Reason code').selectOption('DOCS_CONFIRMED');
  await page.getByRole('button', { name: 'Approve case' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Confirm decision' }).click();
  await expect(page.getByText(/approved with reason DOCS_CONFIRMED/)).toBeVisible();

  const context = await browser.newContext();
  const customer = await context.newPage();
  await login(customer, CUSTOMER, PASSWORD);
  await expect(customer.getByText(/Your account is open: /)).toBeVisible();
  await context.close();
});
