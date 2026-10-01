import { useCallback, useState } from 'react';
import { authApi, casesApi, documentsApi, leadsApi, notificationsApi } from '@/api/resources';
import { ApiError } from '@/api/client';
import { useAuth } from '@/state/AuthContext';
import type { CaseDetail, LeadRequest, Profile, UploadResult } from '@/types';
import { uploadErrorMessage, validateUploadFile } from '@/lib/uploadHelp';
import { useAction, useResource } from './useResource';

export function useLogin() {
  const { signIn } = useAuth();
  const action = useAction();
  const login = useCallback(
    async (username: string, password: string) => {
      const res = await action.run(() => authApi.login(username, password));
      if (res) signIn({ token: res.access_token, role: res.role, caseId: res.case_id });
      return res?.role;
    },
    [action, signIn],
  );
  return { login, busy: action.busy, error: action.error };
}

export function useLeadRegistration() {
  const { signIn } = useAuth();
  const action = useAction();
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const register = useCallback(
    async (lead: LeadRequest) => {
      setFieldErrors({});
      try {
        const res = await action.run(async () => {
          try {
            return await leadsApi.create(lead);
          } catch (e) {
            if (e instanceof ApiError && e.code === 'VALIDATION_ERROR') {
              const fields = (e.details.fields ?? []) as { field: string; message: string }[];
              setFieldErrors(Object.fromEntries(fields.map((f) => [f.field, f.message])));
            }
            throw e;
          }
        });
        if (res) signIn({ token: res.access_token, role: 'prospect', caseId: res.case_id });
        return res;
      } catch {
        return undefined;
      }
    },
    [action, signIn],
  );
  return { register, busy: action.busy, error: action.error, fieldErrors };
}

export function useCase(caseId: string | null) {
  return useResource(() => casesApi.get(caseId as string), `case:${caseId}`, Boolean(caseId));
}

export function useNotifications(caseId: string | null) {
  return useResource(async () => (await notificationsApi.list(caseId as string)).notifications, `notif:${caseId}`, Boolean(caseId));
}

export function useProfileSave(caseId: string) {
  const action = useAction();
  const save = useCallback((profile: Profile) => action.run(() => casesApi.updateProfile(caseId, profile)), [action, caseId]);
  return { save, busy: action.busy, error: action.error, code: action.code };
}

export interface UploadFeedback {
  result?: UploadResult;
  error?: string;
  uploading?: boolean;
}

// Per-item upload with immediate classification feedback (AC-02/AC-03/AC-09.3).
export function useChecklistUpload(caseId: string, onChanged: () => void) {
  const [feedback, setFeedback] = useState<Record<string, UploadFeedback>>({});
  const submitAction = useAction();

  const upload = useCallback(
    async (itemCode: string, file: File) => {
      const invalid = validateUploadFile(file);
      if (invalid) {
        setFeedback((f) => ({ ...f, [itemCode]: { error: invalid } }));
        return;
      }
      setFeedback((f) => ({ ...f, [itemCode]: { uploading: true } }));
      try {
        const result = await documentsApi.upload(caseId, itemCode, file);
        setFeedback((f) => ({ ...f, [itemCode]: { result } }));
        onChanged();
      } catch (e) {
        const msg = e instanceof ApiError ? uploadErrorMessage(e) : uploadErrorMessage({ status: -1, code: '', message: '' });
        setFeedback((f) => ({ ...f, [itemCode]: { error: msg } }));
      }
    },
    [caseId, onChanged],
  );

  const submit = useCallback(async () => {
    const res = await submitAction.run(() => documentsApi.submit(caseId));
    if (res) onChanged();
    return res;
  }, [caseId, onChanged, submitAction]);

  return { feedback, upload, submit, submitting: submitAction.busy, submitError: submitAction.error, submitCode: submitAction.code };
}

export type { CaseDetail };
