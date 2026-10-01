import { expect, test } from '@playwright/test';
import { installLogin, json, loginAs } from './mockApi';
import { expectVisual } from './visual';

const reports = {
  tat: { filters: {}, items: [
    { product: 'Savings', count: 120, avg_seconds: 2700, min_seconds: 480, max_seconds: 9000 },
    { product: 'Current', count: 45, avg_seconds: 4200, min_seconds: 900, max_seconds: 14400 },
    { product: 'NRE', count: 30, avg_seconds: 5400, min_seconds: 1200, max_seconds: 18000 } ] },
  funnel: { filters: {}, stages: [
    { stage: 'INITIATED', count: 250, conversion_bp: 10000 },
    { stage: 'DOCS_SUBMITTED', count: 210, conversion_bp: 8400 },
    { stage: 'SCREENED', count: 205, conversion_bp: 9762 },
    { stage: 'CLASSIFIED', count: 200, conversion_bp: 9756 },
    { stage: 'MANUAL_REVIEW', count: 70, conversion_bp: 3500 },
    { stage: 'APPROVED', count: 160, conversion_bp: 8000 },
    { stage: 'REJECTED', count: 35, conversion_bp: 1750 } ] },
  backlog: { filters: {}, count: 9, oldest_age_minutes: 1600, buckets: [
    { label: 'under_60', min_minutes: 0, max_minutes: 59, count: 3 },
    { label: '60_to_1440', min_minutes: 60, max_minutes: 1440, count: 4 },
    { label: 'over_1440', min_minutes: 1441, max_minutes: null, count: 2 } ] },
  'time-per-stage': { filters: {}, stages: [
    { from_state: 'INITIATED', to_state: 'DOCS_SUBMITTED', count: 210, avg_seconds: 1200 },
    { from_state: 'DOCS_SUBMITTED', to_state: 'SCREENED', count: 205, avg_seconds: 30 },
    { from_state: 'SCREENED', to_state: 'CLASSIFIED', count: 200, avg_seconds: 20 } ] },
  'rejection-reasons': { filters: {}, items: [
    { reason_code: 'RISK_TOO_HIGH', count: 15 }, { reason_code: 'CONFIRMED_WATCHLIST_MATCH', count: 12 }, { reason_code: 'DOCS_INSUFFICIENT', count: 8 } ] },
  'auto-approval': { filters: {}, auto_approved: 160, decided: 195, rate_bp: 8205, target_bp: 6000, met: true },
  'dropped-leads': { older_than_days: 7, total: 11, stages: [{ stage: 'INITIATED', count: 8 }, { stage: 'DOCS_SUBMITTED', count: 3 }] },
};

test.describe('admin console', () => {
  test('AC-10.10: dashboard shows seven panels, each with an accessible table, and filters refresh them', async ({ page }) => {
    await installLogin(page);
    const seen: string[] = [];
    await page.route('**/api/v1/admin/reports/*', (route) => {
      const url = new URL(route.request().url());
      seen.push(url.search);
      const key = url.pathname.split('/').pop() as keyof typeof reports;
      const body = url.searchParams.get('product') === 'NRE' && key === 'tat'
        ? { filters: {}, items: [reports.tat.items[2]] }
        : reports[key];
      return json(route, 200, body);
    });
    await loginAs(page, 'admin1');

    await expect(page.getByRole('heading', { name: 'Operational reports' })).toBeVisible();
    for (const title of ['Turnaround time by product', 'Approval funnel', 'Manual-review backlog', 'Average time per stage', 'Top rejection reasons', 'Auto-approval rate', 'Dropped leads']) {
      const panel = page.getByRole('region', { name: title });
      await expect(panel).toBeVisible();
      await expect(panel.getByRole('table')).toBeVisible();
      await expect(panel.getByRole('img')).toBeVisible();
    }
    const tat = page.getByRole('table', { name: 'Turnaround time by product (table)' });
    await expect(tat.getByRole('row', { name: /Savings/ })).toContainText('45 min 0 s');
    await expect(page.getByRole('table', { name: 'Approval funnel (table)' }).getByRole('row', { name: /Docs submitted/ })).toContainText('84.00%');
    await expect(page.getByText(/Target met/)).toBeVisible();
    await expect(page.getByRole('table', { name: 'Top rejection reasons (table)' })).toContainText('RISK_TOO_HIGH');
    await expectVisual(page, 'reports-dashboard.png', { fullPage: true });

    await page.getByLabel('Product', { exact: true }).selectOption('NRE');
    await expect(tat.getByRole('row')).toHaveCount(2);
    await expect(tat).not.toContainText('Savings');
    expect(seen.some((s) => s.includes('product=NRE'))).toBe(true);
  });

  test('AC-10: empty data shows explicit empty states', async ({ page }) => {
    await installLogin(page);
    await page.route('**/api/v1/admin/reports/*', (route) => {
      const key = new URL(route.request().url()).pathname.split('/').pop();
      const empty: Record<string, unknown> = {
        tat: { items: [] }, funnel: { stages: [] }, backlog: { count: 0, oldest_age_minutes: 0, buckets: [] },
        'time-per-stage': { stages: [] }, 'rejection-reasons': { items: [] },
        'auto-approval': { auto_approved: 0, decided: 0, rate_bp: 0, target_bp: 6000, met: false },
        'dropped-leads': { older_than_days: 7, total: 0, stages: [] },
      };
      return json(route, 200, empty[key as string]);
    });
    await loginAs(page, 'admin1');
    await expect(page.getByText('No data for the selected filters.').first()).toBeVisible();
    await expect(page.getByText('No rejections.')).toBeVisible();
  });

  test('AC-06: rule sets can be drafted and published; watchlist entries can be added and deactivated (AC-05)', async ({ page }) => {
    await installLogin(page);
    let published = false;
    let created = false;
    const draft = { version: 2, status: 'DRAFT', author: 'admin1', created_at: '2026-10-01T00:00:00Z', published_at: null };
    await page.route('**/api/v1/admin/rule-sets', (route) => {
      if (route.request().method() === 'POST') { created = true; return json(route, 201, { ...draft, weights: { age: 20, income_band: 25, occupation_category: 30, geography: 25 }, points: {}, geography_map: {}, geography_default: 'FOREIGN_STANDARD', border_states: [], thresholds: { low_max: 29, medium_max: 59 } }); }
      return json(route, 200, { items: [{ version: 1, status: 'PUBLISHED', author: 'admin', created_at: '2026-10-01T00:00:00Z', published_at: '2026-10-01T00:00:00Z' }, ...(!created ? [] : published ? [{ ...draft, status: 'PUBLISHED', published_at: '2026-10-01T01:00:00Z' }] : [draft])] });
    });
    await page.route('**/api/v1/admin/rule-sets/2/publish', (route) => { published = true; return json(route, 200, { ...draft, status: 'PUBLISHED', published_at: '2026-10-01T01:00:00Z' }); });
    let active = true;
    await page.route('**/api/v1/admin/watchlist', (route) => {
      if (route.request().method() === 'POST') return json(route, 201, {});
      return json(route, 200, { watchlist_version: 3, items: [{ entry_id: 'e1', name: 'Test Person Two', aliases: ['T Two'], list_type: 'AML', active, added_at: '2026-10-01T00:00:00Z', deactivated_at: null }] });
    });
    await page.route('**/api/v1/admin/watchlist/e1/deactivate', (route) => { active = false; return json(route, 200, {}); });

    await loginAs(page, 'admin1');
    await page.getByRole('link', { name: 'Rule sets' }).click();
    await expect(page.getByRole('heading', { name: 'Admin: rule sets' })).toBeVisible();
    await page.getByRole('button', { name: 'Create draft from latest' }).click();
    await expect(page.getByRole('heading', { name: 'Edit draft version 2' })).toBeVisible();
    await page.getByLabel('Weight: age').fill('30');
    await page.getByRole('button', { name: 'Save draft' }).click();
    await expect(page.getByText('Weights must sum to 100 (currently 110).')).toBeVisible();
    await page.getByRole('button', { name: 'Publish v2' }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Publish' }).click();
    await expect(page.getByText(/version 2 published/)).toBeVisible();

    await page.getByRole('link', { name: 'Watchlist' }).click();
    await expect(page.getByRole('cell', { name: 'Test Person Two', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Deactivate Test Person Two' }).click();
    await expect(page.getByRole('cell', { name: 'Deactivated', exact: true })).toBeVisible();
  });
});
