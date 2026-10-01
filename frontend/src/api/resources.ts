import { request, requestBlob } from './client';
import type {
  CaseDetail,
  CaseQuery,
  SignupOptions,
  SignupResponse,
  CaseList,
  CaseListQuery,
  DocumentView,
  Evidence,
  LeadRequest,
  LeadResponse,
  LoginResponse,
  Notification,
  OverrideRequest,
  OverrideResponse,
  Product,
  Profile,
  ReviewQueue,
  RiskAssessment,
  RiskBand,
  UploadResult,
} from '@/types';

export const authApi = {
  login: (username: string, password: string) =>
    request<LoginResponse>('/auth/login', { method: 'POST', body: { username, password }, auth: false }),
  signupOptions: () => request<SignupOptions>('/auth/signup-options', { auth: false }),
  signup: (username: string, password: string, role: string) =>
    request<SignupResponse>('/auth/signup', { method: 'POST', body: { username, password, role }, auth: false }),
};

export const leadsApi = {
  // `withAuth` sends the bearer token so a signed-in prospect account owns the case (AC-14.3).
  create: (lead: LeadRequest, idempotencyKey?: string, withAuth = false) =>
    request<LeadResponse>('/leads', {
      method: 'POST',
      body: lead,
      auth: withAuth,
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
    }),
};

export const casesApi = {
  list: (q: CaseListQuery) =>
    request<CaseList>('/cases', { query: { state: q.state, product: q.product, sort: q.sort, page: q.page, page_size: q.page_size } }),
  get: (id: string) => request<CaseDetail>(`/cases/${id}`),
  updateProfile: (id: string, profile: Profile) => request<CaseDetail>(`/cases/${id}/profile`, { method: 'PUT', body: profile }),
  evidence: (id: string) => request<Evidence>(`/cases/${id}/evidence`),
  checklist: (product: Product) => request<{ product: Product; version: number; items: unknown[] }>(`/products/${product}/checklist`),
};

export const documentsApi = {
  file: (caseId: string, documentId: string) => requestBlob(`/cases/${caseId}/documents/${documentId}/file`),
  upload: (caseId: string, checklistItem: string, file: File) => {
    const form = new FormData();
    form.append('checklist_item', checklistItem);
    form.append('file', file);
    return request<UploadResult>(`/cases/${caseId}/documents`, { method: 'POST', form });
  },
  list: (caseId: string) => request<{ case_id: string; documents: DocumentView[] }>(`/cases/${caseId}/documents`),
  reject: (caseId: string, documentId: string, reasonCode: string, comment?: string) =>
    request<{ document_id: string; status: 'REJECTED'; reason_code: string }>(`/cases/${caseId}/documents/${documentId}/reject`, {
      method: 'POST',
      body: { reason_code: reasonCode, comment },
    }),
  submit: (caseId: string) => request<{ case_id: string; state: string; missing_items: string[] }>(`/cases/${caseId}/submit`, { method: 'POST' }),
};

export const pipelineApi = {
  advance: (caseId: string) =>
    request<{ case_id: string; state: string; steps_run: string[] }>(`/cases/${caseId}/advance`, { method: 'POST' }),
};

export const reviewApi = {
  queue: () => request<ReviewQueue>('/review-queue'),
  override: (caseId: string, body: OverrideRequest) =>
    request<OverrideResponse>(`/cases/${caseId}/override`, { method: 'POST', body }),
  reclassify: (caseId: string, band: RiskBand, reasonCode: string, comment?: string) =>
    request<RiskAssessment>(`/cases/${caseId}/reclassify`, { method: 'POST', body: { band, reason_code: reasonCode, comment } }),
};

export const notificationsApi = {
  list: (caseId: string) => request<{ case_id: string; notifications: Notification[] }>(`/cases/${caseId}/notifications`),
};

export const queriesApi = {
  list: (caseId: string) => request<{ items: CaseQuery[] }>(`/cases/${caseId}/queries`),
  raise: (caseId: string, message: string) => request<CaseQuery>(`/cases/${caseId}/queries`, { method: 'POST', body: { message } }),
  respond: (caseId: string, queryId: string, message: string) => request<CaseQuery>(`/cases/${caseId}/queries/${queryId}/responses`, { method: 'POST', body: { message } }),
  close: (caseId: string, queryId: string) => request<CaseQuery>(`/cases/${caseId}/queries/${queryId}/close`, { method: 'POST' }),
};
