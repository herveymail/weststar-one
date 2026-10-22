import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes, useParams } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RES } from '@ws/shared';
import './styles.css';
import { AuthProvider, useAuth, useCan } from './lib/auth';
import { ToastProvider } from './components/ui';
import { Shell } from './components/Shell';
import { ResourceList } from './components/Resource';
import { Gate } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { TicketsPage } from './pages/Tickets';
import { ClientDetail, ClientsPage } from './pages/Clients';
import { HRAdmin, MyHR } from './pages/HR';
import { SettingsHome, SettingsPageView } from './pages/Settings';
import { Profile } from './pages/Profile';
import { ApiError } from './lib/api';

const qc = new QueryClient({
  defaultOptions: {
    queries: { retry: (n, e) => !(e instanceof ApiError && e.status < 500) && n < 2, refetchOnWindowFocus: false },
  },
});

function ModulePage() {
  const { res } = useParams();
  const can = useCan();
  const r = res ? RES[res] : undefined;
  if (!r || r.hidden) return <div className="page"><h1>Page not found</h1><p className="desc">That page does not exist.</p></div>;
  if (!can(r.area) && !r.ownerScoped) return <div className="page"><h1>{r.label}</h1><p className="banner">You do not have access to {r.label}. Ask an admin if you need it.</p></div>;
  return <div className="page"><ResourceList key={r.id} res={r.id} /></div>;
}

function App() {
  const { me } = useAuth();
  const gate = <Gate />;
  if (!me.user || !me.mfaPassed || me.user.must_change_password || me.mfaSetupRequired) return gate;
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/tickets" element={<TicketsPage />} />
        <Route path="/tickets/:id" element={<TicketsPage />} />
        <Route path="/clients" element={<ClientsPage />} />
        <Route path="/clients/:id" element={<ClientDetail />} />
        <Route path="/my-hr" element={<MyHR />} />
        <Route path="/employees" element={<HRAdmin />} />
        <Route path="/settings" element={<SettingsHome />} />
        <Route path="/settings/:page" element={<SettingsPageView />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/:res" element={<ModulePage />} />
      </Routes>
    </Shell>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <ToastProvider>
          <AuthProvider><App /></AuthProvider>
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
