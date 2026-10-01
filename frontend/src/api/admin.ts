import { request } from './client';
import type {
  AutoApprovalReport,
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
