import { expect, test, type Page } from '@playwright/test';
import { API, expectNoSeriousAxe, login, seedCase } from './helpers';

// AC-16: staff can open the files a customer uploaded. Runs on the default stack after the
// other suites (file order); it creates its own cases.
test.describe.configure({ mode: 'serial' });

// The synthetic upload body written by seedCase and the UI helpers.
const PDF_MARKER = '%PDF-1.4 synthetic';

// Headless Chromium downloads a blob PDF instead of rendering it, so the test captures the blob the
// app fetched (bytes and content type) and still requires that a new tab was opened for it.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    const w = window as unknown as { __blobs: Blob[] };
    w.__blobs = [];
    const create = URL.createObjectURL.bind(URL);
    URL.createObjectURL = (blob: Blob | MediaSource) => {
      if (blob instanceof Blob) w.__blobs.push(blob);
      return create(blob);
    };
  });
});

async function openAndRead(page: Page, buttonName: string | RegExp): Promise<{ text: string; type: string }> {
  const [popup] = await Promise.all([page.waitForEvent('popup'), page.getByRole('button', { name: buttonName }).click()]);
  await expect.poll(() => page.evaluate(() => (window as unknown as { __blobs: Blob[] }).__blobs.length)).toBeGreaterThan(0);
  const result = await page.evaluate(async () => {
    const blobs = (window as unknown as { __blobs: Blob[] }).__blobs;
    const last = blobs[blobs.length - 1];
    return { text: await last.text(), type: last.type };
  });
  await popup.close();
  return result;
}

test('the KYC analyst opens the customer documents from the case page', async ({ page }) => {
  const c = await seedCase({ name: 'Test Person Docs', contact: '9999999931', product: 'Savings', submit: false, docs: 'all' });
  await login(page, 'analyst1');
  await page.goto(`/staff/cases/${c.caseId}`);
  const table = page.getByRole('table', { name: 'Current documents' });
  await expect(table).toBeVisible();
  await expect(table.getByRole('button', { name: /^View / })).toHaveCount(3);
  const id = await openAndRead(page, 'View ID proof (version 1)');
  expect(id.text).toContain(PDF_MARKER);
  expect(id.type).toBe('application/pdf');
  expect((await openAndRead(page, 'View Address proof (version 1)')).text).toContain(PDF_MARKER);
  await expectNoSeriousAxe(page);
});

test('the analyst can also open an earlier version after the customer re-uploads', async ({ page }) => {
  const c = await seedCase({ name: 'Test Person Reupload', contact: '9999999932', product: 'Savings', submit: false, docs: 'two' });
  const form = new FormData();
  form.append('checklist_item', 'ID_PROOF');
  form.append('file', new Blob(['%PDF-1.4 synthetic second version'], { type: 'application/pdf' }), 'pan_second.pdf');
  const res = await fetch(`${API}/cases/${c.caseId}/documents`, { method: 'POST', headers: { Authorization: `Bearer ${c.token}` }, body: form });
  expect(res.status).toBe(201);
  await login(page, 'analyst1');
  await page.goto(`/staff/cases/${c.caseId}`);
  const earlier = page.getByRole('table', { name: 'Earlier versions (replaced by a newer upload)' });
  await expect(earlier).toBeVisible();
  expect((await openAndRead(page, 'View ID proof (version 1, replaced)')).text).toContain(PDF_MARKER);
  expect((await openAndRead(page, 'View ID proof (version 2)')).text).toContain('second version');
});

test('the compliance officer opens the documents of a case waiting for review', async ({ page }) => {
  const c = await seedCase({ name: 'Test Person One', contact: '9999999933', product: 'Savings', submit: true, docs: 'all' });
  await login(page, 'officer1', 'demo-officer1-pass');
  await expect(page.getByRole('heading', { name: 'Manual review queue' })).toBeVisible();
  await page.getByRole('button', { name: new RegExp(`^Review ${c.caseId.slice(0, 8)}`) }).click();
  expect((await openAndRead(page, 'View ID proof (version 1)')).text).toContain(PDF_MARKER);
  expect((await openAndRead(page, 'View Photograph (version 1)')).text).toContain(PDF_MARKER);
});

test('a different customer cannot read someone elses document through the API', async () => {
  const owner = await seedCase({ name: 'Test Person Owner', contact: '9999999934', product: 'Savings', submit: false, docs: 'two' });
  const other = await seedCase({ name: 'Test Person Other', contact: '9999999935', product: 'Savings', submit: false });
  const list = (await (await fetch(`${API}/cases/${owner.caseId}/documents`, { headers: { Authorization: `Bearer ${owner.token}` } })).json()) as { documents: { document_id: string }[] };
  const url = `${API}/cases/${owner.caseId}/documents/${list.documents[0].document_id}/file`;
  expect((await fetch(url, { headers: { Authorization: `Bearer ${owner.token}` } })).status).toBe(200);
  expect((await fetch(url, { headers: { Authorization: `Bearer ${other.token}` } })).status).toBe(403);
  expect((await fetch(url)).status).toBe(401);
});
