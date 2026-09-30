import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { setAccessToken, setUnauthorizedHandler } from '@/api/client';
import type { Role } from '@/types';

export interface Session {
  token: string;
  role: Role;
  caseId: string | null;
}

interface AuthValue {
  session: Session | null;
  signIn: (s: Session) => void;
  signOut: () => void;
}

const STORAGE_KEY = 'onboardx.session';
const AuthContext = createContext<AuthValue | null>(null);

export function loadSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as Session;
    return s.token && s.role ? s : null;
  } catch {
    return null;
  }
}

function persist(s: Session | null): void {
  try {
    if (s) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(s));
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // storage unavailable: session lives in memory only
  }
}

export function AuthProvider({ children, initial }: { children: ReactNode; initial?: Session | null }) {
  const [session, setSession] = useState<Session | null>(() => {
    const s = initial !== undefined ? initial : loadSession();
    setAccessToken(s?.token ?? null);
    return s;
  });

  const signIn = useCallback((s: Session) => {
    setAccessToken(s.token);
    persist(s);
    setSession(s);
  }, []);

  const signOut = useCallback(() => {
    setAccessToken(null);
    persist(null);
    setSession(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(signOut);
    return () => setUnauthorizedHandler(null);
  }, [signOut]);

  const value = useMemo(() => ({ session, signIn, signOut }), [session, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
