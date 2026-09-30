import { useCallback, useEffect, useRef, useState } from 'react';
import { describeError } from '@/api/client';

export interface Resource<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

// Loads data whenever `key` changes. `key` must encode every input of `fetcher`.
export function useResource<T>(fetcher: () => Promise<T>, key: string, enabled = true): Resource<T> {
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetcherRef
      .current()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(describeError(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [key, enabled, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload };
}

export interface Action {
  busy: boolean;
  error: string | null;
  code: string | null;
  run: <T>(fn: () => Promise<T>) => Promise<T | undefined>;
  clear: () => void;
}

// Wraps a mutation: tracks busy/error state and never throws to the caller.
export function useAction(): Action {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true);
    setError(null);
    setCode(null);
    try {
      return await fn();
    } catch (e) {
      setError(describeError(e));
      setCode(typeof e === 'object' && e !== null && 'code' in e ? String((e as { code: unknown }).code) : null);
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);
  const clear = useCallback(() => {
    setError(null);
    setCode(null);
  }, []);
  return { busy, error, code, run, clear };
}
