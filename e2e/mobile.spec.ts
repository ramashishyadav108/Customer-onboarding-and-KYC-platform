import { expect, test } from '@playwright/test';
import { ProspectMock, pdf } from './mockApi';
import { expectVisual } from './visual';

test.use({ viewport: { width: 375, height: 812 } });

async function noHorizontalScroll(page: import('@playwright/test').Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

test.describe('prospect portal at 375px', () => {
  test('AC-01.7: registration form fits the viewport with touch-sized controls', async ({ page }) => {
    await new ProspectMock().install(page);
    await page.goto('/portal/register');
    await noHorizontalScroll(page);
    const button = page.getByRole('button', { name: 'Start application' });
    const box = await button.boundingBox();
    expect(box?.height).toBeGreaterThanOrEqual(44);
    expect(box?.width).toBeGreaterThan(300);
    await expectVisual(page, 'mobile-register.png');
  });

  test('AC-02: checklist and status pages have no horizontal scroll on mobile', async ({ page }) => {
    const mock = new ProspectMock();
    await mock.install(page);
    await page.goto('/portal/register');
    await page.getByLabel('Full name').fill('Meera Nair');
    await page.getByLabel('Contact (phone or email)').fill('meera.nair@example.com');
    await page.getByLabel('Account type').selectOption('Savings');
    await page.getByRole('button', { name: 'Start application' }).click();
    await page.getByLabel('Date of birth').fill('1990-04-12');
    await page.getByLabel('Annual income (INR)').fill('3000000');
    await page.getByLabel('Occupation').selectOption('SALARIED');
    await page.getByLabel(/State code/).fill('MH');
    await page.getByRole('button', { name: 'Save and continue' }).click();
    await expect(page.getByRole('heading', { name: 'Upload your documents' })).toBeVisible();
    await page.getByLabel('Upload ID proof').setInputFiles(pdf('pan_valid.pdf'));
    await expect(page.getByText('Classified as PAN: verified')).toBeVisible();
    await noHorizontalScroll(page);
    await expectVisual(page, 'mobile-checklist.png', { fullPage: true });

    await page.getByRole('link', { name: '3 Status' }).click();
    await expect(page.getByRole('heading', { name: 'Application status' })).toBeVisible();
    await noHorizontalScroll(page);
    await expectVisual(page, 'mobile-status.png', { fullPage: true });
  });

  test('NFR-04: skip link is the first focusable element', async ({ page }) => {
    await new ProspectMock().install(page);
    await page.goto('/portal/register');
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused();
  });
});
