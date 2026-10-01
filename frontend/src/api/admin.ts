import { request } from './client';
import type {
  AutoApprovalReport,
  ChecklistItemSpec,
  ChecklistVersion,
  ManagedUser,
  NewUser,
  StaffRole,
  Product,
  DroppedLeadsReport,
  BacklogReport,
  FunnelReport,
  ReportFilters,
  RejectionReasonsReport,
  Reports,
  RuleSet,
  RuleSetSummary,
  RuleSetUpdate,
  TatReport,
  TimePerStageReport,
  WatchlistEntry,
  WatchlistNew,
} from '@/types';

export const ruleSetsApi = {
  list: () => request<{ items: RuleSetSummary[] }>('/admin/rule-sets'),
  get: (version: number) => request<RuleSet>(`/admin/rule-sets/${version}`),
  createDraft: () => request<RuleSet>('/admin/rule-sets', { method: 'POST' }),
  update: (version: number, body: RuleSetUpdate) => request<RuleSet>(`/admin/rule-sets/${version}`, { method: 'PUT', body }),
  publish: (version: number) => request<RuleSet>(`/admin/rule-sets/${version}/publish`, { method: 'POST' }),
};

export const watchlistApi = {
  list: () => request<{ watchlist_version: number; items: WatchlistEntry[] }>('/admin/watchlist'),
  add: (entry: WatchlistNew) => request<WatchlistEntry>('/admin/watchlist', { method: 'POST', body: entry }),
  deactivate: (entryId: string) => request<WatchlistEntry>(`/admin/watchlist/${entryId}/deactivate`, { method: 'POST' }),
};

export const reportsApi = {
  async all(f: ReportFilters): Promise<Reports> {
    const query = { product: f.product, from: f.from, to: f.to };
    const get = <T>(p: string) => request<T>(`/admin/reports/${p}`, { query });
    const [tat, funnel, backlog, timePerStage, rejections, autoApproval, droppedLeads] = await Promise.all([
      get<TatReport>('tat'),
      get<FunnelReport>('funnel'),
      get<BacklogReport>('backlog'),
      get<TimePerStageReport>('time-per-stage'),
      get<RejectionReasonsReport>('rejection-reasons'),
      get<AutoApprovalReport>('auto-approval'),
      get<DroppedLeadsReport>('dropped-leads'),
    ]);
    return { tat, funnel, backlog, timePerStage, rejections, autoApproval, droppedLeads };
  },
};

export const usersApi = {
  list: () => request<{ items: ManagedUser[] }>('/admin/users'),
  create: (user: NewUser) => request<ManagedUser>('/admin/users', { method: 'POST', body: user }),
  changeRole: (userId: string, role: StaffRole) => request<ManagedUser>(`/admin/users/${userId}/role`, { method: 'PUT', body: { role } }),
  deactivate: (userId: string) => request<ManagedUser>(`/admin/users/${userId}/deactivate`, { method: 'POST' }),
  reactivate: (userId: string) => request<ManagedUser>(`/admin/users/${userId}/reactivate`, { method: 'POST' }),
  approve: (userId: string, role?: StaffRole) => request<ManagedUser>(`/admin/users/${userId}/approve`, { method: 'POST', body: role ? { role } : undefined }),
  reject: (userId: string) => request<ManagedUser>(`/admin/users/${userId}/reject`, { method: 'POST' }),
};

export const checklistsApi = {
  list: () => request<{ items: ChecklistVersion[] }>('/admin/checklists'),
  publish: (product: Product, items: ChecklistItemSpec[]) => request<ChecklistVersion>(`/admin/checklists/${product}`, { method: 'POST', body: { items } }),
};
