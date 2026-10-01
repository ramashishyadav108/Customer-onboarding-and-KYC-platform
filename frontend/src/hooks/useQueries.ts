import { useCallback } from 'react';
import { queriesApi } from '@/api/resources';
import { useAction, useResource } from './useResource';

// Analyst queries on one case: list plus raise, respond and close actions (AC-13).
export function useCaseQueries(caseId: string | null) {
  const list = useResource(async () => (await queriesApi.list(caseId as string)).items, `queries:${caseId}`, Boolean(caseId));
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
  const raise = useCallback((message: string) => wrap(() => queriesApi.raise(caseId as string, message)), [wrap, caseId]);
  const respond = useCallback((queryId: string, message: string) => wrap(() => queriesApi.respond(caseId as string, queryId, message)), [wrap, caseId]);
  const close = useCallback((queryId: string) => wrap(() => queriesApi.close(caseId as string, queryId)), [wrap, caseId]);
  return { list, raise, respond, close, busy: action.busy, error: action.error, clear: action.clear };
}
