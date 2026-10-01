import { expect, test, type Page } from '@playwright/test';
import { API, expectNoSeriousAxe, login, pdf, seedCase } from './helpers';

// Live-backend evaluation of UI groups F (prospect), H (staff), J (review), L (dashboard).
// Serial: the first test needs an empty database.
test.describe.configure({ mode: 'serial' });

const PANELS = ['Turnaround time by product', 'Approval funnel', 'Manual-review backlog', 'Average time per stage', 'Top rejection reasons', 'Auto-approval rate'];

test('F170: dashboard on an empty database shows empty-state messages', async ({ page }) => {
  await login(page, 'admin1');
  await expect(page.getByRole('heading', { name: 'Operational reports' })).toBeVisible();
  for (const t of PANELS) await expect(page.getByRole('region', { name: t })).toBeVisible();
  await expect(page.getByText('No data for the selected filters.').first()).toBeVisible();
  await expect(page.getByText('No rejections.')).toBeVisible();
});

let clean: { caseId: string; token: string };
let hit: { caseId: string; token: string };
let nre: { caseId: string; token: string };

test('seed cases through the real API', async () => {
  clean = await seedCase({ name: 'Test Person Alpha', contact: '9999999701', product: 'Savings', submit: true, docs: 'all' });
  hit = await seedCase({ name: 'Test Person One', contact: '9999999702', product: 'Savings', submit: true, docs: 'all' });
  nre = await seedCase({ name: 'Test Person Gamma', contact: '9999999703', product: 'NRE', submit: false });
  await seedCase({ name: 'Test Person Delta', contact: '9999999704', product: 'Current', submit: false });
});

async function register(page: Page, name: string, contact: string) {
  await page.goto('/portal/register');
  await page.getByLabel('Full name').fill(name);
  await page.getByLabel('Contact (phone or email)').fill(contact);
  await page.getByLabel('Account type').selectOption('Savings');
  await page.getByRole('button', { name: 'Start application' }).click();
}

async function profile(page: Page) {
  await expect(page.getByRole('heading', { name: 'Your profile' })).toBeVisible();
  await page.getByLabel('Date of birth').fill('1990-04-12');
  await page.getByLabel('Annual income (INR)').fill('3000000');
  await page.getByLabel('Occupation').selectOption('SELF_EMPLOYED');
  await page.getByLabel(/State code/).fill('MH');
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await expect(page.getByRole('heading', { name: 'Upload your documents' })).toBeVisible();
}

// Presses Tab (at most 4 times, e.g. past a date picker button) until the labelled control has focus.
async function tabTo(page: Page, label: string | RegExp) {
  for (let i = 0; i < 4; i++) {
    await page.keyboard.press('Tab');
    if (await page.getByLabel(label).evaluate((el) => el === document.activeElement)) return;
  }
  throw new Error(`Could not reach ${String(label)} using Tab`);
}

async function asProspect(page: Page, c: { caseId: string; token: string }) {
  await page.goto('/portal/register');
  await page.evaluate(([t, id]) => sessionStorage.setItem('onboardx.session', JSON.stringify({ token: t, role: 'prospect', caseId: id })), [c.token, c.caseId]);
}

test.describe('group F: prospect portal', () => {
  test('F069: inline errors linked by aria-describedby, then case_id shown on success', async ({ page }) => {
    await page.goto('/portal/register');
    await page.getByRole('button', { name: 'Start application' }).click();
    const name = page.getByLabel('Full name');
    await expect(name).toHaveAttribute('aria-invalid', 'true');
    const ref = await name.getAttribute('aria-describedby');
    expect(ref).toBeTruthy();
    await expect(page.locator(`[id="${ref!.split(" ")[0]}"]`)).toContainText('Enter your full name.');
    await register(page, 'Test Person Epsilon', '9999999705');
    await profile(page);
    await page.goto('/portal/status');
    await expect(page.locator('code')).toHaveText(/^[0-9a-f]{8}-[0-9a-f]{4}-/);
  });

  test('F070: checklist gates Submit and chips update after upload', async ({ page }) => {
    await register(page, 'Test Person Zeta', '9999999706');
    await profile(page);
    const submit = page.getByRole('button', { name: 'Submit documents' });
    await expect(submit).toBeDisabled();
    for (const code of ['ID_PROOF', 'ADDRESS_PROOF', 'PHOTOGRAPH']) await expect(page.getByTestId(`item-${code}`)).toContainText('Missing');
    await page.getByLabel('Upload ID proof').setInputFiles(pdf('pan_valid.pdf'));
    await expect(page.getByTestId('item-ID_PROOF')).toContainText('Verified');
    await page.getByLabel('Upload Address proof').setInputFiles(pdf('utility-bill_valid.pdf'));
    await page.getByLabel('Upload Photograph').setInputFiles(pdf('photograph_valid.pdf'));
    await expect(submit).toBeEnabled();
    await submit.focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { name: 'Application status' })).toBeVisible();
  });

  test('F074: registration and profile completable with keyboard only', async ({ page }) => {
    await page.goto('/portal/register');
    await page.getByLabel('Full name').focus();
    await page.keyboard.type('Test Person Eta');
    await page.keyboard.press('Tab');
    await page.keyboard.type('9999999707');
    await page.keyboard.press('Tab');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { name: 'Your profile' })).toBeVisible();
    await page.getByLabel('Date of birth').focus();
    await page.keyboard.type('12041990'); // day-first locale in headless Chromium
    await tabTo(page, 'Annual income (INR)');
    await page.keyboard.type('3000000');
    await tabTo(page, 'Occupation');
    await page.keyboard.press('ArrowDown');
    await tabTo(page, 'Country code');
    await page.keyboard.type('in');
    await tabTo(page, /State code/);
    await page.keyboard.type('mh');
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { name: 'Upload your documents' })).toBeVisible();
  });

  test('F071: status page in-place re-upload of a FLAGGED item', async ({ page }) => {
    const c = await seedCase({ name: 'Test Person Theta', contact: '9999999708', product: 'Savings', submit: false, docs: 'two' });
    const fd = new FormData();
    fd.append('checklist_item', 'PHOTOGRAPH');
    fd.append('file', new Blob(['%PDF-1.4 x'], { type: 'application/pdf' }), 'random.pdf');
    await fetch(`${API}/cases/${c.caseId}/documents`, { method: 'POST', headers: { Authorization: `Bearer ${c.token}` }, body: fd });
    await asProspect(page, c);
    await page.goto('/portal/status');
    const row = page.getByTestId('action-PHOTOGRAPH');
    await expect(row).toContainText('Flagged');
    const before = await page.locator('code').textContent();
    await row.getByLabel('Re-upload Photograph').setInputFiles(pdf('photograph_valid.pdf'));
    await expect(page.getByText(/Photograph: classified as PHOTOGRAPH, verified/)).toBeVisible();
    await expect(page.getByTestId('action-PHOTOGRAPH')).toHaveCount(0);
    await expect(page.locator('code')).toHaveText(before!);
    await expect(page.getByRole('heading', { name: 'Application status' })).toBeVisible();
  });

  for (const w of [360, 1280]) {
    test(`F072: no horizontal overflow at ${w}px`, async ({ page }) => {
      await page.setViewportSize({ width: w, height: 800 });
      await register(page, 'Test Person Iota', `99999997${w === 360 ? '09' : '10'}`);
      await profile(page);
      for (const path of ['/portal/profile', '/portal/documents', '/portal/status']) {
        await page.goto(path);
        await page.waitForLoadState('networkidle');
        const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        expect(over, path).toBeLessThanOrEqual(0);
      }
      await page.getByRole('button', { name: 'Sign out' }).click();
      await page.waitForLoadState('networkidle');
      expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth), '/portal/register').toBeLessThanOrEqual(0);
    });
  }

  test('F073: axe on lead, upload and status pages', async ({ page }) => {
    await page.goto('/portal/register');
    await expectNoSeriousAxe(page);
    await register(page, 'Test Person Kappa', '9999999711');
    await profile(page);
    await expectNoSeriousAxe(page);
    await page.goto('/portal/status');
    await expect(page.getByRole('heading', { name: 'Application status' })).toBeVisible();
    await expectNoSeriousAxe(page);
  });
});

test.describe('group H: staff workbench and admin', () => {
  test('F108: workbench filters by state and product', async ({ page }) => {
    await login(page, 'analyst1');
    await expect(page.getByRole('heading', { name: 'Analyst workbench' })).toBeVisible();
    await page.getByLabel('State').selectOption('INITIATED');
    await page.getByLabel('Product').selectOption('NRE');
    const body = page.getByRole('table').getByRole('row').filter({ hasNot: page.getByRole('columnheader') });
    await expect(page.getByRole('link', { name: nre.caseId.slice(0, 8) })).toBeVisible();
    const texts = await body.allInnerTexts();
    expect(texts.length).toBeGreaterThanOrEqual(1);
    for (const t of texts) {
      expect(t).toContain('NRE');
      expect(t).toMatch(/initiated/i);
    }
    await page.getByLabel('Product').selectOption('Current');
    await expect(body.first()).toContainText('Current');
    await expect(page.getByRole('link', { name: nre.caseId.slice(0, 8) })).toHaveCount(0);
  });

  test('F109: case detail shows documents, screening and risk evidence', async ({ page }) => {
    await login(page, 'analyst1');
    await page.goto(`/staff/cases/${clean.caseId}`);
    await expect(page.getByRole('heading', { name: 'Case detail' })).toBeVisible();
    const main = page.locator('main');
    await expect(main).toContainText('PAN');
    await expect(main).toContainText(/Verified/i);
    await expect(main).toContainText(/screening/i);
    await expect(main).toContainText(/score/i);
    await expect(main).toContainText(/low|medium|high/i);
    await expect(main).toContainText(/version/i);
  });

  test('F110: reject-document requires a reason, then row becomes REJECTED', async ({ page }) => {
    const c = await seedCase({ name: 'Test Person Lambda', contact: '9999999712', product: 'Savings', submit: false, docs: 'all' });
    await login(page, 'analyst1');
    await page.goto(`/staff/cases/${c.caseId}`);
    await page.getByRole('button', { name: /^Reject / }).first().click();
    await page.getByRole('button', { name: 'Confirm rejection' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.getByLabel('Reason code').selectOption('DOC_ILLEGIBLE');
    await page.getByRole('button', { name: 'Confirm rejection' }).click();
    await expect(page.getByText(/Document rejected \(DOC_ILLEGIBLE\)/)).toBeVisible();
    await expect(page.locator('main')).toContainText(/Rejected/i);
  });

  test('F111: published rule versions are read-only; a created draft is editable', async ({ page }) => {
    await login(page, 'admin1');
    await page.goto('/admin/rule-sets');
    await expect(page.getByText('Immutable').first()).toBeVisible();
    await expect(page.getByRole('textbox')).toHaveCount(0);
    await page.getByRole('button', { name: 'Create draft from latest' }).click();
    await expect(page.getByLabel('Weight: age')).toBeEnabled();
  });

  test('F112: admin adds a watchlist entry and sees it listed', async ({ page }) => {
    await login(page, 'admin1');
    await page.goto('/admin/watchlist');
    await page.getByLabel('Name', { exact: true }).fill('Sample Evaluator Entry');
    await page.getByLabel('Aliases (comma separated)').fill('S E Entry');
    await page.getByRole('button', { name: 'Add entry' }).click();
    await expect(page.getByRole('cell', { name: 'Sample Evaluator Entry', exact: true })).toBeVisible();
  });

  test('F113: axe on staff pages; contact masked to last 2 characters', async ({ page }) => {
    await login(page, 'admin1');
    for (const path of ['/staff/workbench', `/staff/cases/${clean.caseId}`, '/admin/rule-sets', '/admin/watchlist']) {
      await page.goto(path);
      await page.waitForLoadState('networkidle');
      await expectNoSeriousAxe(page);
    }
    await page.goto(`/staff/cases/${clean.caseId}`);
    await expect(page.locator('main')).toContainText('********01');
    expect(await page.locator('main').innerText()).not.toContain('9999999701');
  });
});

test.describe('group J: manual review', () => {
  test('F145 F147 F148 F150: queue, reason-gated decision, dialog focus, approval removes case', async ({ page }) => {
    await login(page, 'officer1');
    await expect(page.getByRole('heading', { name: 'Manual review queue' })).toBeVisible();
    await expect(page.getByText(/AML_HIT/).first()).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Waiting' })).toBeVisible();
    await page.getByRole('button', { name: new RegExp(`Review ${hit.caseId.slice(0, 8)}`) }).click();
    const approve = page.getByRole('button', { name: 'Approve case' });
    await expect(approve).toBeDisabled();
    await page.getByLabel('Reason code').selectOption('FALSE_POSITIVE_CLEARED');
    await expect(approve).toBeEnabled();
    await expectNoSeriousAxe(page);
    await approve.focus();
    await page.keyboard.press('Enter');
    const dialog = page.getByRole('dialog', { name: 'Record approval' });
    await expect(dialog).toBeVisible();
    expect(await page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]'))).toBe(true);
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(approve).toBeFocused();
    await approve.click();
    await dialog.getByRole('button', { name: 'Confirm decision' }).click();
    await expect(page.getByText(/approved with reason FALSE_POSITIVE_CLEARED/)).toBeVisible();
    await expect(page.getByText(/account/i).first()).toBeVisible();
    await expect(page.getByRole('button', { name: new RegExp(`Review ${hit.caseId.slice(0, 8)}`) })).toHaveCount(0);
  });

  test('F146: analyst opening the review route is sent to the forbidden page', async ({ page }) => {
    await login(page, 'analyst1');
    await page.goto('/staff/review');
    await expect(page.getByRole('heading', { name: '403 Forbidden' })).toBeVisible();
  });

  test('F149: prospect sees notification history newest first', async ({ page }) => {
    const api = (await (await fetch(`${API}/cases/${hit.caseId}/notifications`, { headers: { Authorization: `Bearer ${hit.token}` } })).json()) as { notifications: { event: string; created_at: string }[] };
    expect(api.notifications.length).toBeGreaterThanOrEqual(2);
    await asProspect(page, hit);
    await page.goto('/portal/status');
    const items = page.getByRole('list', { name: 'Notifications' }).getByRole('listitem');
    await expect(items).toHaveCount(api.notifications.length);
    const newest = [...api.notifications].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
    await expect(items.first()).toContainText(newest.event.split('_').map((w, i) => (i === 0 ? w[0] + w.slice(1).toLowerCase() : w.toLowerCase())).join(' '));
  });
});

test.describe('group L: admin dashboard', () => {
  test('F167 F169: panels, API-equal values, table and text alternatives', async ({ page }) => {
    await login(page, 'admin1');
    const apiAuto = page.waitForResponse((r) => r.url().includes('/admin/reports/auto-approval'));
    await page.goto('/admin/dashboard');
    const api = (await (await apiAuto).json()) as { auto_approved: number; decided: number };
    for (const t of PANELS) {
      const panel = page.getByRole('region', { name: t });
      await expect(panel.getByRole('table')).toBeVisible();
      await expect(panel.getByRole('img')).toBeVisible();
      expect((await panel.innerText()).length).toBeGreaterThan(20);
    }
    const auto = page.getByRole('table', { name: 'Auto-approval rate (table)' });
    await expect(auto.getByRole('row', { name: /Auto-approved/ })).toContainText(String(api.auto_approved));
    await expect(auto.getByRole('row', { name: /Decided/ })).toContainText(String(api.decided));
  });

  test('F168: product and date filters are sent for every panel and values refresh', async ({ page }) => {
    await login(page, 'admin1');
    const seen: string[] = [];
    page.on('request', (r) => {
      if (r.url().includes('/admin/reports/')) seen.push(r.url());
    });
    await page.goto('/admin/dashboard');
    await expect(page.getByRole('region', { name: 'Approval funnel' })).toBeVisible();
    seen.length = 0;
    await page.getByLabel('Product', { exact: true }).selectOption('NRE');
    await page.getByLabel('From').fill('2020-01-01');
    await page.getByLabel('To').fill('2099-12-31');
    await expect.poll(() => seen.filter((u) => u.includes('product=NRE') && u.includes('from=2020-01-01') && u.includes('to=2099-12-31')).length).toBeGreaterThanOrEqual(6);
  });

  test('F171: dashboard axe, keyboard reachable controls, admin-only', async ({ page }) => {
    await login(page, 'admin1');
    await page.goto('/admin/dashboard');
    await expect(page.getByRole('region', { name: 'Approval funnel' })).toBeVisible();
    await expectNoSeriousAxe(page);
    await page.getByLabel('Product', { exact: true }).focus();
    await page.keyboard.press('Tab');
    await expect(page.getByLabel('From')).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.getByLabel('To')).toBeFocused();
    await page.getByRole('button', { name: 'Sign out' }).click();
    await login(page, 'analyst1');
    await page.goto('/admin/dashboard');
    await expect(page.getByRole('heading', { name: '403 Forbidden' })).toBeVisible();
  });
});
