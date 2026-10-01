import { expect, test, type Page } from '@playwright/test';
import { err, installLogin, json, loginAs } from './mockApi';
import { expectVisual } from './visual';

const CASE = 'aaaaaaaa-1111-2222-3333-444444444444';

const evidence = {
  case_id: CASE, state: 'MANUAL_REVIEW', product: 'Savings',
  documents: [
    { document_id: 'd1', checklist_item: 'ID_PROOF', version: 1, status: 'VERIFIED', doc_class: 'PAN', reason_code: null, confidence_bp: 9500, rule_version: 1, superseded: false, size_bytes: 1000, sha256: 'ab12', uploaded_at: '2026-10-01T09:30:00Z' },
    { document_id: 'd2', checklist_item: 'ADDRESS_PROOF', version: 1, status: 'VERIFIED', doc_class: 'UTILITY_BILL', reason_code: null, confidence_bp: 9500, rule_version: 1, superseded: false, size_bytes: 1200, sha256: 'cd34', uploaded_at: '2026-10-01T09:31:00Z' },
  ],
  screening: { id: 's1', case_id: CASE, hits: [{ entry_id: 'e1', list_type: 'AML', reason_code: 'AML_HIT' }], requires_manual_review: true, watchlist_version: 2, screened_at: '2026-10-01T09:32:00Z' },
  risk_assessment: { assessment_id: 'r1', case_id: CASE, score: 35, band: 'MEDIUM', rule_version: 1, source: 'RULE_ENGINE', created_at: '2026-10-01T09:33:00Z', breakdown: [
    { factor: 'age', value_label: '25-60', points: 0, weight: 20, contribution: 0 },
    { factor: 'income_band', value_label: 'B3', points: 30, weight: 25, contribution: 750 },
    { factor: 'occupation_category', value_label: 'SELF_EMPLOYED', points: 30, weight: 30, contribution: 900 },
    { factor: 'geography', value_label: 'DOMESTIC', points: 0, weight: 25, contribution: 0 } ] },
  decision: { decision_id: 'dec1', case_id: CASE, type: 'AUTO', outcome: 'MANUAL_REVIEW', reason_code: 'AML_HIT', rule_version: 1, actor: 'system', created_at: '2026-10-01T09:34:00Z' },
  override: null, review_reason_code: 'AML_HIT', account_number_masked: null,
};

async function installCompliance(page: Page, sink: { override?: unknown }) {
  let inQueue = true;
  await installLogin(page);
  await page.route('**/api/v1/review-queue', (route) =>
    json(route, 200, { total: inQueue ? 1 : 0, items: inQueue ? [{ case_id: CASE, product: 'Savings', reason_code: 'AML_HIT', age_minutes: 125, entered_review_at: '2026-10-01T09:34:00Z' }] : [] }));
  await page.route(`**/api/v1/cases/${CASE}/evidence`, (route) => json(route, 200, evidence));
  await page.route(`**/api/v1/cases/${CASE}/override`, (route) => {
    const body = route.request().postDataJSON() as { decision: string; reason_code: string };
    sink.override = body;
    if (!body.reason_code) return err(route, 422, 'UNKNOWN_REASON_CODE', 'Reason required');
    inQueue = false;
    return json(route, 200, { case_id: CASE, state: 'APPROVED', account_number: 'SAV123456789012', override: { override_id: 'o1', case_id: CASE, actor: 'officer1', previous_state: 'MANUAL_REVIEW', decision: body.decision, reason_code: body.reason_code, comment: null, rule_version: 1, created_at: '2026-10-01T10:00:00Z' } });
  });
}

test.describe('compliance officer', () => {
  test('AC-08.7: reviews a MANUAL_REVIEW case and overrides with a reason code', async ({ page }) => {
    const sink: { override?: unknown } = {};
    await installCompliance(page, sink);
    await loginAs(page, 'officer1');

    await expect(page.getByRole('heading', { name: 'Manual review queue' })).toBeVisible();
    await expect(page.getByText(/AML_HIT - Possible AML/)).toBeVisible();
    await page.getByRole('button', { name: /Review aaaaaaaa/ }).click();
    await expect(page.getByRole('heading', { name: 'Review panel' })).toBeVisible();
    await expect(page.getByText('AML hit - AML_HIT')).toBeVisible();
    await expectVisual(page, 'review-panel.png', { fullPage: true });

    const approve = page.getByRole('button', { name: 'Approve case' });
    await expect(approve).toBeDisabled();
    await page.getByLabel('Reason code').selectOption('FALSE_POSITIVE_CLEARED');
    await expect(approve).toBeEnabled();
    await approve.click();

    const dialog = page.getByRole('dialog', { name: 'Record approval' });
    await expect(dialog).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await approve.click();
    await dialog.getByRole('button', { name: 'Confirm decision' }).click();

    await expect(page.getByText(/approved with reason FALSE_POSITIVE_CLEARED.*audit trail/)).toBeVisible();
    await expect(page.getByText('No cases are waiting for manual review.')).toBeVisible();
    expect(sink.override).toEqual({ decision: 'APPROVE', reason_code: 'FALSE_POSITIVE_CLEARED' });
  });

  test('NFR-04: a prospect-only page is forbidden for the compliance officer', async ({ page }) => {
    await installCompliance(page, {});
    await loginAs(page, 'officer1');
    await page.goto('/admin/dashboard');
    await expect(page.getByRole('heading', { name: '403 Forbidden' })).toBeVisible();
  });

  test('NFR-04: wrong credentials show an error', async ({ page }) => {
    await installLogin(page);
    await loginAs(page, 'nobody');
    await expect(page.getByRole('alert')).toContainText('Invalid credentials');
  });
});
