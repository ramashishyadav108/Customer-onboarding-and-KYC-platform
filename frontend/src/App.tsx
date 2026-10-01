import { Navigate, Route, Routes } from 'react-router-dom';
import { ROLE_HOME, ROUTES } from '@/config';
import { AppShell } from '@/components/AppShell';
import { RequireRole } from '@/state/RequireRole';
import { useAuth } from '@/state/AuthContext';
import { ForbiddenPage } from '@/pages/ForbiddenPage';
import { LeadFormPage } from '@/pages/prospect/LeadFormPage';
import { ProfilePage } from '@/pages/prospect/ProfilePage';
import { UploadPage } from '@/pages/prospect/UploadPage';
import { StatusPage } from '@/pages/prospect/StatusPage';
import { LoginPage } from '@/pages/staff/LoginPage';
import { SignupPage } from '@/pages/prospect/SignupPage';
import { WorkbenchPage } from '@/pages/staff/WorkbenchPage';
import { CaseDetailPage } from '@/pages/staff/CaseDetailPage';
import { ReviewQueuePage } from '@/pages/staff/ReviewQueuePage';
import { DashboardPage } from '@/pages/admin/DashboardPage';
import { RuleSetsPage } from '@/pages/admin/RuleSetsPage';
import { WatchlistPage } from '@/pages/admin/WatchlistPage';
import { UsersPage } from '@/pages/admin/UsersPage';
import { ChecklistsPage } from '@/pages/admin/ChecklistsPage';

function Home() {
  const { session } = useAuth();
  return <Navigate to={session ? ROLE_HOME[session.role] : ROUTES.register} replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path={ROUTES.login} element={<LoginPage />} />
      <Route path={ROUTES.signup} element={<SignupPage />} />
      <Route path={ROUTES.forbidden} element={<ForbiddenPage />} />

      <Route element={<AppShell title="OnboardX - Open your account" />}>
        <Route path={ROUTES.register} element={<LeadFormPage />} />
        <Route path={ROUTES.profile} element={<RequireRole roles={['prospect']}><ProfilePage /></RequireRole>} />
        <Route path={ROUTES.documents} element={<RequireRole roles={['prospect']}><UploadPage /></RequireRole>} />
        <Route path={ROUTES.status} element={<RequireRole roles={['prospect']}><StatusPage /></RequireRole>} />
      </Route>

      <Route element={<AppShell title="OnboardX Staff Console" wide />}>
        <Route path={ROUTES.workbench} element={<RequireRole roles={['kyc-analyst', 'admin']}><WorkbenchPage /></RequireRole>} />
        <Route path="/staff/cases/:caseId" element={<RequireRole roles={['kyc-analyst', 'admin']}><CaseDetailPage /></RequireRole>} />
        <Route path={ROUTES.reviewQueue} element={<RequireRole roles={['compliance-officer']}><ReviewQueuePage /></RequireRole>} />
        <Route path={ROUTES.dashboard} element={<RequireRole roles={['admin']}><DashboardPage /></RequireRole>} />
        <Route path={ROUTES.ruleSets} element={<RequireRole roles={['admin']}><RuleSetsPage /></RequireRole>} />
        <Route path={ROUTES.watchlist} element={<RequireRole roles={['admin']}><WatchlistPage /></RequireRole>} />
        <Route path={ROUTES.users} element={<RequireRole roles={['admin']}><UsersPage /></RequireRole>} />
        <Route path={ROUTES.checklists} element={<RequireRole roles={['admin']}><ChecklistsPage /></RequireRole>} />
      </Route>

      <Route path="*" element={<Home />} />
    </Routes>
  );
}
