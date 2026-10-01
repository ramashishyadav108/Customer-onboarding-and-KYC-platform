import { useCallback } from 'react';
import { reportsApi, ruleSetsApi, watchlistApi } from '@/api/admin';
import type { ReportFilters, RuleSetUpdate, WatchlistNew } from '@/types';
import { useAction, useResource } from './useResource';

export function useReports(f: ReportFilters) {
  return useResource(() => reportsApi.all(f), `reports:${f.product}:${f.from}:${f.to}`);
}

export function useRuleSets() {
  const list = useResource(() => ruleSetsApi.list(), 'rulesets');
  const action = useAction();
  const { reload } = list;

  const createDraft = useCallback(async () => {
    const r = await action.run(() => ruleSetsApi.createDraft());
    if (r) reload();
    return r;
  }, [action, reload]);
  const saveDraft = useCallback(
    async (version: number, body: RuleSetUpdate) => {
      const r = await action.run(() => ruleSetsApi.update(version, body));
      if (r) reload();
      return r;
    },
    [action, reload],
  );
  const publish = useCallback(
    async (version: number) => {
      const r = await action.run(() => ruleSetsApi.publish(version));
      if (r) reload();
      return r;
    },
    [action, reload],
  );
  const load = useCallback((version: number) => action.run(() => ruleSetsApi.get(version)), [action]);
  return { list, createDraft, saveDraft, publish, load, busy: action.busy, error: action.error, clear: action.clear };
}

export function useWatchlist() {
  const list = useResource(() => watchlistApi.list(), 'watchlist');
  const action = useAction();
  const { reload } = list;
  const add = useCallback(
    async (entry: WatchlistNew) => {
      const r = await action.run(() => watchlistApi.add(entry));
      if (r) reload();
      return r;
    },
    [action, reload],
  );
  const deactivate = useCallback(
    async (id: string) => {
      const r = await action.run(() => watchlistApi.deactivate(id));
      if (r) reload();
      return r;
    },
    [action, reload],
  );
  return { list, add, deactivate, busy: action.busy, error: action.error };
}
