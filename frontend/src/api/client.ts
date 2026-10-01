import { API_BASE } from '@/config';
import type { ApiErrorBody } from '@/types';

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;
  readonly correlationId: string | null;

  constructor(status: number, code: string, message: string, details: Record<string, unknown>, correlationId: string | null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
    this.correlationId = correlationId;
  }
}

let accessToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

export function newCorrelationId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `cid-${Date.now()}-${Math.floor(Math.random() * 1e9)}`;
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  form?: FormData;
  query?: Record<string, string | number | undefined | null>;
  auth?: boolean;
  headers?: Record<string, string>;
}

export function buildQuery(query?: RequestOptions['query']): string {
  if (!query) return '';
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v));
  }
  const s = params.toString();
  return s ? `?${s}` : '';
}

async function parseError(res: Response, correlationId: string | null): Promise<ApiError> {
  let body: Partial<ApiErrorBody> | null = null;
  try {
    body = (await res.json()) as Partial<ApiErrorBody>;
  } catch {
    body = null;
  }
  const err = body?.error;
  return new ApiError(
    res.status,
    err?.code ?? 'UNKNOWN_ERROR',
    err?.message ?? `Request failed with status ${res.status}`,
    err?.details ?? {},
    correlationId,
  );
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json', 'X-Correlation-ID': newCorrelationId(), ...opts.headers };
  if (opts.auth !== false && accessToken) headers.Authorization = `Bearer ${accessToken}`;
  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form;
  } else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}${buildQuery(opts.query)}`, { method: opts.method ?? 'GET', headers, body });
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'Cannot reach the server. Check your connection and try again.', {}, headers['X-Correlation-ID']);
  }
  const correlationId = res.headers.get('X-Correlation-ID') ?? headers['X-Correlation-ID'];
  if (!res.ok) {
    const err = await parseError(res, correlationId);
    if (res.status === 401 && opts.auth !== false && unauthorizedHandler) unauthorizedHandler();
    throw err;
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// Fetches a binary response (an uploaded document) with the bearer token; errors use the API envelope.
export async function requestBlob(path: string): Promise<Blob> {
  const headers: Record<string, string> = { 'X-Correlation-ID': newCorrelationId() };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { headers });
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'Cannot reach the server. Check your connection and try again.', {}, headers['X-Correlation-ID']);
  }
  if (!res.ok) {
    const err = await parseError(res, res.headers.get('X-Correlation-ID') ?? headers['X-Correlation-ID']);
    if (res.status === 401 && unauthorizedHandler) unauthorizedHandler();
    throw err;
  }
  return res.blob();
}

export function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    const ref = e.correlationId ? ` (ref ${e.correlationId.slice(0, 8)})` : '';
    return `${e.message}${ref}`;
  }
  return e instanceof Error ? e.message : 'Something went wrong.';
}
