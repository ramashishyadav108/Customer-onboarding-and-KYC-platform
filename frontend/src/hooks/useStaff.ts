import { useCallback } from 'react';
import { casesApi, documentsApi, pipelineApi, reviewApi } from '@/api/resources';
import type { CaseListQuery, OverrideRequest, RiskBand } from '@/types';
import { useAction, useResource } from './useResource';

export function useCaseList(q: CaseListQuery) {
  return useResource(() => casesApi.list(q), `cases:${q.state}:${q.product}:${q.sort}:${q.page}:${q.page_size}`);
}

export function useEvidence(caseId: string | null) {
  return useResource(() => casesApi.evidence(caseId as string), `evidence:${caseId}`, Boolean(caseId));
}

export function useStaffCase(caseId: string | null) {
  return useResource(() => casesApi.get(caseId as string), `staffcase:${caseId}`, Boolean(caseId));
}

export function useReviewQueue() {
  return useResource(() => reviewApi.queue(), 'review-queue');
}

export function useDocumentReview(caseId: string, onDone: () => void) {
  const action = useAction();
  const reject = useCallback(
    async (documentId: string, reasonCode: string, comment?: string) => {
      const res = await action.run(() => documentsApi.reject(caseId, documentId, reasonCode, comment));
      if (res) onDone();
      return res;
    },
    [action, caseId, onDone],
  );
  const advance = useCallback(async () => {
    const res = await action.run(() => pipelineApi.advance(caseId));
    if (res) onDone();
    return res;
  }, [action, caseId, onDone]);
  return { reject, advance, busy: action.busy, error: action.error, clear: action.clear };
}

export function useOverride(caseId: string, onDone: () => void) {
  const action = useAction();
  const override = useCallback(
    async (body: OverrideRequest) => {
      const res = await action.run(() => reviewApi.override(caseId, body));
      if (res) onDone();
      return res;
    },
    [action, caseId, onDone],
  );
  const reclassify = useCallback(
    async (band: RiskBand, reason: string, comment?: string) => {
      const res = await action.run(() => reviewApi.reclassify(caseId, band, reason, comment));
      if (res) onDone();
      return res;
    },
    [action, caseId, onDone],
  );
  return { override, reclassify, busy: action.busy, error: action.error, clear: action.clear };
}
