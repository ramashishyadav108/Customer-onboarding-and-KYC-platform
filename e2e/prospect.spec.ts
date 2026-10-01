import { expect, test, type Page } from '@playwright/test';
import { CASE_ID, ProspectMock, pdf } from './mockApi';

async function register(page: Page) {
  await page.goto('/portal/register');
  await page.getByLabel('Full name').fill('Meera Nair');
  await page.getByLabel('Contact (phone or email)').fill('9876543221');
  await page.getByLabel('Account type').selectOption('Savings');
  await page.getByRole('button', { name: 'Start application' }).click();
}

async function completeProfile(page: Page) {
  await expect(page.getByRole('heading', { name: 'Your profile' })).toBeVisible();
  await page.getByLabel('Date of birth').fill('1990-04-12');
  await page.getByLabel('Annual income (INR)').fill('3000000');
  await page.getByLabel('Occupation').selectOption('SELF_EMPLOYED');
  await page.getByLabel(/State code/).fill('MH');
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await expect(page.getByRole('heading', { name: 'Upload your documents' })).toBeVisible();
}

test.describe('prospect portal', () => {
  let mock: ProspectMock;
  test.beforeEach(async ({ page }) => {
    mock = new ProspectMock();
    await mock.install(page);
  });

  test('AC-01: registers a lead and lands on the profile step', async ({ page }) => {
    await page.goto('/portal/register');
    await page.getByRole('button', { name: 'Start application' }).click();
    await expect(page.getByText('Enter your full name.')).toBeVisible();
    await expect(page).toHaveScreenshot('register-validation.png');
    await register(page);
    await expect(page.getByRole('heading', { name: 'Your profile' })).toBeVisible();
    expect(mock.leadBody).toEqual({ name: 'Meera Nair', contact: '9876543221', product: 'Savings' });
  });

  test('AC-06: profile requires a state code for India', async ({ page }) => {
    await register(page);
    await page.getByLabel('Date of birth').fill('1990-04-12');
    await page.getByLabel('Annual income (INR)').fill('3000000');
    await page.getByLabel('Occupation').selectOption('SALARIED');
    await page.getByRole('button', { name: 'Save and continue' }).click();
    await expect(page.getByText(/two-letter state code/)).toBeVisible();
    await page.getByLabel('Country code').fill('gb');
    await expect(page.getByLabel(/State code/)).toHaveCount(0);
  });

  test('AC-02 AC-03: checklist shows classification feedback and missing documents block submit', async ({ page }) => {
    await register(page);
    await completeProfile(page);
    const submit = page.getByRole('button', { name: 'Submit documents' });
    await expect(submit).toBeDisabled();
    await expect(page.getByText(/Still missing: ID proof, Address proof, Photograph/)).toBeVisible();

    await page.getByLabel('Upload ID proof').setInputFiles(pdf('pan_valid.pdf'));
    await expect(page.getByText('Classified as PAN: verified')).toBeVisible();
    await page.getByLabel('Upload Address proof').setInputFiles(pdf('unknown_scan.pdf'));
    await expect(page.getByText(/flagged for review \(DOC_UNRECOGNISED\)/)).toBeVisible();
    await expect(submit).toBeDisabled();
    await expect(page.getByText(/Still missing: Photograph/)).toBeVisible();
    await expect(page).toHaveScreenshot('checklist-partial.png');

    await page.getByLabel('Upload Photograph').setInputFiles(pdf('photograph_valid.pdf'));
    await expect(submit).toBeEnabled();
    expect(mock.submitCalls).toBe(0);
  });

  test('AC-02: a disallowed file type is rejected before upload', async ({ page }) => {
    await register(page);
    await completeProfile(page);
    await page.getByLabel('Upload ID proof').setInputFiles({ name: 'bad_type.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('MZ') });
    await expect(page.getByText('Only PDF, JPG or PNG files are accepted.')).toBeVisible();
  });

  test('AC-09: status timeline shows reason codes, notifications and supports re-upload', async ({ page }) => {
    await register(page);
    await completeProfile(page);
    await page.getByLabel('Upload ID proof').setInputFiles(pdf('pan_valid.pdf'));
    await page.getByLabel('Upload Address proof').setInputFiles(pdf('utility-bill_valid.pdf'));
    await page.getByLabel('Upload Photograph').setInputFiles(pdf('photograph_valid.pdf'));
    await page.getByRole('button', { name: 'Submit documents' }).click();

    await expect(page.getByRole('heading', { name: 'Application status' })).toBeVisible();
    const timeline = page.getByRole('list', { name: 'Application progress' });
    await expect(timeline.locator('[aria-current="step"]')).toContainText('Documents submitted');
    await expect(page.getByRole('list', { name: 'Notifications' })).toContainText('Docs submitted');

    // Server-side events: analyst rejects a document, then the case goes to manual review.
    mock.rejectDocument('ADDRESS_PROOF', 'DOC_EXPIRED');
    mock.moveTo('MANUAL_REVIEW', 'AML_HIT');
    await page.getByRole('button', { name: 'Refresh status' }).click();
    await expect(timeline.locator('[aria-current="step"]')).toContainText('Under manual review');
    await expect(timeline).toContainText('AML_HIT');
    await expect(page.getByRole('list', { name: 'Notifications' })).toContainText('Reason: DOC_EXPIRED');
    await expect(page.getByText(/Action required on 1 document/)).toBeVisible();
    await expect(page).toHaveScreenshot('status-timeline.png');

    // Re-upload the rejected item without restarting the case.
    await page.getByRole('link', { name: 'Go to documents' }).click();
    await expect(page.getByText(/Action required: Address proof \(rejected\)/)).toBeVisible();
    await page.getByLabel('Upload Address proof').setInputFiles(pdf('utility-bill_v2.pdf'));
    await expect(page.getByText('Classified as UTILITY_BILL: verified')).toBeVisible();
    expect(CASE_ID).toBeTruthy();
  });
});
