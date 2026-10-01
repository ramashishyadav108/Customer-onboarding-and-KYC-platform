import type { Page, Route } from '@playwright/test';

export const CASE_ID = '3f0c2c9e-7a54-4b7e-9d3e-5b1f6a2e9c10';
const T0 = '2026-10-01T09:30:00Z';

type Item = {
  item_code: string;
  mandatory: boolean;
  accepted_classes: string[];
  status: 'MISSING' | 'VERIFIED' | 'FLAGGED' | 'REJECTED';
  document_id: string | null;
  doc_version: number | null;
  doc_class: string | null;
  reason_code: string | null;
};

const json = (route: Route, status: number, body: unknown) =>
  route.fulfill({ status, contentType: 'application/json', headers: { 'X-Correlation-ID': 'e2e-corr-0001' }, body: JSON.stringify(body) });

const err = (route: Route, status: number, code: string, message: string, details: unknown = {}) =>
  json(route, status, { error: { code, message, details } });

export function classify(filename: string): { doc_class: string; status: 'VERIFIED' | 'FLAGGED'; reason_code: string | null } {
  const f = filename.toLowerCase();
  if (f.startsWith('pan')) return { doc_class: 'PAN', status: 'VERIFIED', reason_code: null };
  if (f.startsWith('utility')) return { doc_class: 'UTILITY_BILL', status: 'VERIFIED', reason_code: null };
  if (f.startsWith('photograph')) return { doc_class: 'PHOTOGRAPH', status: 'VERIFIED', reason_code: null };
  return { doc_class: 'UNRECOGNISED', status: 'FLAGGED', reason_code: 'DOC_UNRECOGNISED' };
}

// Stateful in-memory stand-in for the prospect-facing API (AC-01, AC-02, AC-03, AC-09).
export class ProspectMock {
  state = 'INITIATED';
  items: Item[] = [
    { item_code: 'ID_PROOF', mandatory: true, accepted_classes: ['PAN', 'AADHAAR', 'PASSPORT'], status: 'MISSING', document_id: null, doc_version: null, doc_class: null, reason_code: null },
    { item_code: 'ADDRESS_PROOF', mandatory: true, accepted_classes: ['UTILITY_BILL', 'AADHAAR'], status: 'MISSING', document_id: null, doc_version: null, doc_class: null, reason_code: null },
    { item_code: 'PHOTOGRAPH', mandatory: true, accepted_classes: ['PHOTOGRAPH'], status: 'MISSING', document_id: null, doc_version: null, doc_class: null, reason_code: null },
  ];
  notifications: { notification_id: string; case_id: string; event: string; template: string; text: string; details: Record<string, string>; created_at: string }[] = [];
  profileSaved = false;
  leadBody: unknown = null;
  submitCalls = 0;

  private notify(event: string, details: Record<string, string> = {}) {
    this.notifications.unshift({ notification_id: `n${this.notifications.length + 1}`, case_id: CASE_ID, event, template: event.toLowerCase(), text: `Your application is now ${event.toLowerCase().replace('_', ' ')}.`, details, created_at: T0 });
  }

  detail() {
    const missing = this.items.filter((i) => i.mandatory && i.status === 'MISSING').map((i) => i.item_code);
    return {
      case_id: CASE_ID, name: 'Meera Nair', contact_masked: '********21', product: 'Savings', state: this.state, checklist_version: 1,
      checklist_items: this.items, missing_items: missing,
      action_required: this.items.filter((i) => i.status === 'MISSING' || i.status === 'REJECTED').map((i) => ({ item_code: i.item_code, status: i.status, reason_code: i.reason_code })),
      profile: null, profile_complete: this.profileSaved, account_number_masked: null, created_at: T0, updated_at: T0,
    };
  }

  // Simulate staff rejecting a document and advancing the pipeline (server-side events).
  rejectDocument(itemCode: string, reason: string) {
    const it = this.items.find((i) => i.item_code === itemCode);
    if (it) { it.status = 'REJECTED'; it.reason_code = reason; }
    this.notify('DOC_REJECTED', { item_code: itemCode, reason_code: reason });
  }
  moveTo(state: string, reason?: string) {
    this.state = state;
    this.notify(state, reason ? { reason_code: reason } : {});
  }

  async install(page: Page) {
    await page.route('**/api/v1/**', async (route) => {
      const req = route.request();
      const url = new URL(req.url());
      const path = url.pathname.replace('/api/v1', '');
      const m = req.method();
      if (m === 'POST' && path === '/leads') {
        this.leadBody = req.postDataJSON();
        this.notify('INITIATED');
        return json(route, 201, { case_id: CASE_ID, state: 'INITIATED', product: (this.leadBody as { product: string }).product, access_token: 'e2e-prospect-token', token_type: 'bearer', expires_in: 1800 });
      }
      if (m === 'GET' && path === `/cases/${CASE_ID}`) return json(route, 200, this.detail());
      if (m === 'PUT' && path === `/cases/${CASE_ID}/profile`) { this.profileSaved = true; return json(route, 200, this.detail()); }
      if (m === 'POST' && path === `/cases/${CASE_ID}/documents`) {
        const body = req.postData() ?? '';
        const item = /name="checklist_item"\r\n\r\n([A-Z_]+)/.exec(body)?.[1] ?? '';
        const filename = /filename="([^"]+)"/.exec(body)?.[1] ?? '';
        const it = this.items.find((i) => i.item_code === item);
        if (!it) return err(route, 422, 'UNKNOWN_CHECKLIST_ITEM', 'Item is not on the checklist', { checklist_item: item });
        if (filename.startsWith('fake_')) return err(route, 415, 'UNSUPPORTED_MEDIA_TYPE', 'File content does not match its declared type');
        const base = classify(filename);
        const mismatch = base.status === 'VERIFIED' && !it.accepted_classes.includes(base.doc_class);
        const c = mismatch ? { doc_class: base.doc_class, status: 'FLAGGED' as const, reason_code: 'DOC_CLASS_MISMATCH' } : base;
        it.status = c.status; it.doc_class = c.doc_class; it.reason_code = c.reason_code; it.doc_version = (it.doc_version ?? 0) + 1; it.document_id = `doc-${item}-${it.doc_version}`;
        return json(route, 201, { document_id: it.document_id, checklist_item: item, version: it.doc_version, ...c, confidence_bp: c.status === 'VERIFIED' ? 9500 : 0, rule_version: 1 });
      }
      if (m === 'POST' && path === `/cases/${CASE_ID}/submit`) {
        this.submitCalls += 1;
        const missing = this.items.filter((i) => i.mandatory && (i.status === 'MISSING' || i.status === 'REJECTED')).map((i) => i.item_code);
        if (missing.length) return err(route, 422, 'MISSING_DOCUMENTS', 'Mandatory documents are missing', { missing_items: missing });
        this.moveTo('DOCS_SUBMITTED');
        return json(route, 200, { case_id: CASE_ID, state: 'DOCS_SUBMITTED', missing_items: [] });
      }
      if (m === 'GET' && path === `/cases/${CASE_ID}/notifications`) return json(route, 200, { case_id: CASE_ID, notifications: this.notifications });
      return err(route, 404, 'NOT_FOUND', `unmocked ${m} ${path}`);
    });
  }
}

export function pdf(name: string) {
  return { name, mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 synthetic') };
}

const STAFF_TOKENS: Record<string, string> = { officer1: 'compliance-officer', admin1: 'admin', analyst1: 'kyc-analyst' };

export async function installLogin(page: Page) {
  await page.route('**/api/v1/auth/login', async (route) => {
    const { username } = route.request().postDataJSON() as { username: string };
    const role = STAFF_TOKENS[username];
    if (!role) return err(route, 401, 'UNAUTHENTICATED', 'Invalid credentials');
    return json(route, 200, { access_token: `e2e-${role}`, token_type: 'bearer', role, expires_in: 1800, case_id: null });
  });
}

export async function loginAs(page: Page, username: string) {
  await page.goto('/login');
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill('synthetic-pass');
  await page.getByRole('button', { name: 'Sign in' }).click();
}

export { json, err };
