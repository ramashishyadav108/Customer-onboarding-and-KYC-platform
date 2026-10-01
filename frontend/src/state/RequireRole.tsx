import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { ROUTES } from '@/config';
import type { Role } from '@/types';
import { useAuth } from './AuthContext';

interface Props {
  roles: Role[];
  children: ReactNode;
  loginPath?: string;
}

// Route guard: anonymous users go to login, wrong-role users go to /forbidden.
export function RequireRole({ roles, children, loginPath = ROUTES.login }: Props) {
  const { session } = useAuth();
  const location = useLocation();
  if (!session) return <Navigate to={loginPath} replace state={{ from: location.pathname }} />;
  if (!roles.includes(session.role)) return <Navigate to={ROUTES.forbidden} replace />;
  return <>{children}</>;
}
