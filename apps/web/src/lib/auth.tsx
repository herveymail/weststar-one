import { createContext, useContext, useEffect, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { Level, PermArea } from '@ws/shared';
import { api, setCsrf } from './api';

export interface Me {
  user: null | { id: number; email: string; name: string; role: string; hr_access: boolean; look: 'indigo' | 'graphite'; mfa_enabled: boolean; must_change_password: boolean; title: string | null; phone: string | null };
  csrfToken?: string; mfaPassed?: boolean; mfaSetupRequired?: boolean;
  perms?: Record<PermArea, Level>;
  app?: { name: string };
}

const Ctx = createContext<{ me: Me; refresh: () => Promise<unknown> } | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ['me'], queryFn: () => api.get<Me>('/api/auth/me'), staleTime: 60_000, refetchOnWindowFocus: true });
  if (q.data?.csrfToken) setCsrf(q.data.csrfToken);
  useEffect(() => {
    const look = q.data?.user?.look ?? 'indigo';
    document.documentElement.dataset.look = look;
  }, [q.data?.user?.look]);
  useEffect(() => {
    const h = () => { qc.invalidateQueries({ queryKey: ['me'] }); };
    window.addEventListener('ws:signed-out', h);
    return () => window.removeEventListener('ws:signed-out', h);
  }, [qc]);
  if (q.isLoading) return <div className="login-wrap"><p className="muted">Loading…</p></div>;
  if (q.isError) return <div className="login-wrap"><p className="banner">Cannot reach the server. Check your connection and reload.</p></div>;
  return <Ctx.Provider value={{ me: q.data ?? { user: null }, refresh: () => q.refetch() }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error('useAuth outside provider');
  return c;
}

const ORDER: Level[] = ['none', 'view', 'edit', 'manage'];
export function useCan() {
  const { me } = useAuth();
  return (area: PermArea, need: Level = 'view') => ORDER.indexOf(me.perms?.[area] ?? 'none') >= ORDER.indexOf(need);
}
