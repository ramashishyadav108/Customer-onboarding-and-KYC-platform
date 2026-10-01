import { Link } from 'react-router-dom';
import { ROLE_HOME, ROUTES } from '@/config';
import { SkipLink } from '@/components/ui';
import { useAuth } from '@/state/AuthContext';

export function ForbiddenPage() {
  const { session } = useAuth();
  return (
    <>
      <SkipLink />
      <header className="top"><h1>OnboardX</h1></header>
      <main id="main" tabIndex={-1}>
        <section className="card" aria-labelledby="h">
          <h2 id="h">403 Forbidden</h2>
          <p>Your role does not have access to this page.</p>
          <p><Link to={session ? ROLE_HOME[session.role] : ROUTES.login}>Go to your home page</Link></p>
        </section>
      </main>
    </>
  );
}
