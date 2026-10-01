import { useCallback } from 'react';
import { checklistsApi, reportsApi, ruleSetsApi, usersApi, watchlistApi } from '@/api/admin';
import type { ChecklistItemSpec, NewUser, Product, ReportFilters, RuleSetUpdate, StaffRole, WatchlistNew } from '@/types';
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

export function useUsers() {
  const list = useResource(() => usersApi.list(), 'users');
  const action = useAction();
  const { reload } = list;
  const wrap = useCallback(
    async <T,>(fn: () => Promise<T>) => {
      const r = await action.run(fn);
      if (r) reload();
      return r;
    },
    [action, reload],
  );
  const create = useCallback((u: NewUser) => wrap(() => usersApi.create(u)), [wrap]);
  const changeRole = useCallback((id: string, role: StaffRole) => wrap(() => usersApi.changeRole(id, role)), [wrap]);
  const deactivate = useCallback((id: string) => wrap(() => usersApi.deactivate(id)), [wrap]);
  const reactivate = useCallback((id: string) => wrap(() => usersApi.reactivate(id)), [wrap]);
  const approve = useCallback((id: string, role?: StaffRole) => wrap(() => usersApi.approve(id, role)), [wrap]);
  const reject = useCallback((id: string) => wrap(() => usersApi.reject(id)), [wrap]);
  return { list, create, changeRole, deactivate, reactivate, approve, reject, busy: action.busy, error: action.error, clear: action.clear };
}

export function useChecklists() {
  const list = useResource(() => checklistsApi.list(), 'checklists');
  const action = useAction();
  const { reload } = list;
  const publish = useCallback(
    async (product: Product, items: ChecklistItemSpec[]) => {
      const r = await action.run(() => checklistsApi.publish(product, items));
      if (r) reload();
      return r;
    },
    [action, reload],
  );
  return { list, publish, busy: action.busy, error: action.error, clear: action.clear };
}
