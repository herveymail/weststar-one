import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { NAV, type NavItem } from '@ws/shared';
import { Icon } from './Icon';
import { useAuth, useCan } from '../lib/auth';
import { api, initials, qs } from '../lib/api';
import { errMsg, useToast } from './ui';
import { NewTicketDialog } from '../pages/Tickets';

const ALWAYS = new Set(['dashboard', 'my_hr']);

function useNav() {
  const can = useCan();
  return useMemo(() => NAV.map((g) => ({ ...g, items: g.items.filter((i) => ALWAYS.has(i.id) || can(i.area, 'view')) })).filter((g) => g.items.length), [can]);
}

function activeFor(path: string, item: NavItem) {
  if (item.path === '/') return path === '/';
  return path === item.path || path.startsWith(item.path + '/');
}

function Sidebar({ openCount, open }: { openCount?: number; open: boolean }) {
  const nav = useNav();
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>(() => { try { return JSON.parse(localStorage.getItem('ws.nav.collapsed') ?? '{}'); } catch { return {}; } });
  useEffect(() => { try { localStorage.setItem('ws.nav.collapsed', JSON.stringify(collapsed)); } catch { /* ignore */ } }, [collapsed]);
  const { pathname } = useLocation();
  const item = (i: NavItem) => (
    <NavLink key={i.id} to={i.path} end={i.path === '/'} className={() => `nav-item ${activeFor(pathname, i) ? 'on' : ''}`}>
      <Icon name={i.icon} />{i.label}
      {i.id === 'tickets' && openCount ? <span className="badge">{openCount}</span> : null}
    </NavLink>
  );
  return (
    <nav className={`side ${open ? 'open' : ''}`} id="main-nav" aria-label="Main">
      <Link to="/" className="brand"><span className="logo">W</span>Weststar ONE</Link>
      {nav.map((g) => g.group === null ? g.items.map(item) : (
        <div key={g.group} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <button className="nav-section" aria-expanded={!collapsed[g.group]} onClick={() => setCollapsed((c) => ({ ...c, [g.group!]: !c[g.group!] }))}>
            <span>{g.group}</span><Icon name="chevron" size={14} />
          </button>
          {!collapsed[g.group] && g.items.map(item)}
        </div>
      ))}
    </nav>
  );
}

function Rail({ open }: { open: boolean }) {
  const nav = useNav();
  const { pathname } = useLocation();
  const [fly, setFly] = useState<string | null>(null);
  useEffect(() => setFly(null), [pathname]);
  const direct = nav.flatMap((g) => (g.group === null || g.items.length === 1 ? g.items : []));
  const groups = nav.filter((g) => g.group && g.items.length > 1);
  const settings = direct.find((i) => i.id === 'settings');
  const flyGroup = groups.find((g) => g.group === fly);
  return (
    <>
      <nav className={`rail ${open ? 'open' : ''}`} id="main-nav" aria-label="Main">
        <Link to="/" className="logo" aria-label="Weststar ONE home">W1</Link>
        {direct.filter((i) => i.id !== 'settings').map((i) => (
          <NavLink key={i.id} to={i.path} end={i.path === '/'} className={() => `rail-item ${activeFor(pathname, i) ? 'on' : ''}`}>
            <Icon name={i.icon} size={20} />{i.id === 'dashboard' ? 'Home' : i.label}
          </NavLink>
        ))}
        {groups.map((g) => {
          const on = fly === g.group || g.items.some((i) => activeFor(pathname, i));
          return (
            <button key={g.group} className={`rail-item ${on ? 'on' : ''}`} aria-expanded={fly === g.group} onClick={() => setFly(fly === g.group ? null : g.group)}>
              <Icon name={g.icon ?? 'tools'} size={20} />{g.short}
            </button>
          );
        })}
        <div style={{ flex: '1 1 auto', minHeight: 12 }} />
        {settings && <NavLink to="/settings" className={() => `rail-item ${pathname.startsWith('/settings') ? 'on' : ''}`}><Icon name="settings" size={20} />Settings</NavLink>}
      </nav>
      {flyGroup && (
        <>
          <button className="fly-shade" aria-label="Close menu" onClick={() => setFly(null)} />
          <div className="fly" role="menu" aria-label={flyGroup.group!}>
            <div className="fly-title">{flyGroup.group}</div>
            {flyGroup.items.map((i) => <NavLink key={i.id} to={i.path} className={() => `nav-item ${activeFor(pathname, i) ? 'on' : ''}`}><Icon name={i.icon} />{i.label}</NavLink>)}
          </div>
        </>
      )}
    </>
  );
}

function JumpSearch() {
  const nav = useNav();
  const navigate = useNavigate();
  const [q, setQ] = useState('');
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  const can = useCan();
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); ref.current?.focus(); setOpen(true); } };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, []);
  const term = q.trim().toLowerCase();
  const pages = term ? nav.flatMap((g) => g.items.map((i) => ({ ...i, group: g.group }))).filter((i) => (i.label + ' ' + (i.group ?? '')).toLowerCase().includes(term)).slice(0, 6) : [];
  const tq = useQuery({
    queryKey: ['jump-tickets', term], enabled: term.length >= 2 && can('tickets'),
    queryFn: () => api.get(`/api/tickets${qs({ q: term, filter: 'all', limit: 5 })}`), staleTime: 10_000,
  });
  const cq = useQuery({
    queryKey: ['jump-clients', term], enabled: term.length >= 2 && can('clients'),
    queryFn: () => api.get(`/api/options/clients${qs({ q: term })}`), staleTime: 10_000,
  });
  const results: { key: string; label: ReactNode; go: () => void; head?: string }[] = [
    ...pages.map((p, i) => ({ key: 'p' + p.id, head: i === 0 ? 'Go to' : undefined, label: <><Icon name={p.icon} size={16} />{p.label}<span className="small muted" style={{ marginLeft: 'auto' }}>{p.group ?? ''}</span></>, go: () => navigate(p.path) })),
    ...((cq.data ?? []) as { id: number; label: string }[]).slice(0, 4).map((c, i) => ({ key: 'c' + c.id, head: i === 0 ? 'Clients' : undefined, label: <><Icon name="clients" size={16} />{c.label}</>, go: () => navigate(`/clients/${c.id}`) })),
    ...((tq.data?.rows ?? []) as any[]).map((t, i) => ({ key: 't' + t.id, head: i === 0 ? 'Tickets' : undefined, label: <><span className="small muted num">{t.number}</span><span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.subject}</span></>, go: () => navigate(`/tickets/${t.id}`) })),
  ];
  const pick = (i: number) => { results[i]?.go(); setQ(''); setOpen(false); ref.current?.blur(); };
  return (
    <div className="search" role="combobox" aria-expanded={open && results.length > 0} aria-haspopup="listbox">
      <Icon name="search" size={16} />
      <label htmlFor="jump" className="sr">Search or jump to a page</label>
      <input id="jump" ref={ref} autoComplete="off" placeholder="Search tickets and clients, or jump to any page…" value={q}
        onChange={(e) => { setQ(e.target.value); setActive(0); setOpen(true); }} onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)); }
          if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          if (e.key === 'Enter') { e.preventDefault(); pick(active); }
          if (e.key === 'Escape') { setQ(''); ref.current?.blur(); }
        }} />
      <span className="kbd">Ctrl K</span>
      {open && term && results.length > 0 && (
        <div className="jump" role="listbox">
          {results.map((r, i) => (
            <div key={r.key}>
              {r.head && <div className="jump-head">{r.head}</div>}
              <button role="option" aria-selected={i === active} className={`jump-item ${i === active ? 'active' : ''}`} style={{ width: '100%' }} onMouseDown={(e) => e.preventDefault()} onClick={() => pick(i)}>{r.label}</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ClockButton() {
  const toast = useToast();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ['clock'], queryFn: () => api.get(`/api/r/timeclock${qs({ status: 'Open', limit: 1 })}`), staleTime: 30_000 });
  const open = (q.data?.rows ?? [])[0];
  const toggle = async () => {
    try {
      if (open) { await api.patch(`/api/r/timeclock/${open.id}`, { data: { clock_out: new Date().toISOString() } }); toast('Clocked out.'); }
      else { await api.post('/api/r/timeclock', { data: { clock_in: new Date().toISOString() } }); toast('Clocked in.'); }
      qc.invalidateQueries({ queryKey: ['clock'] });
    } catch (e) { toast(errMsg(e), 'err'); }
  };
  return <button className="btn" onClick={toggle}><Icon name="clock" size={16} />{open ? 'Clock out' : 'Clock in'}</button>;
}

function UserMenu() {
  const { me } = useAuth();
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const signOut = async () => { try { await api.post('/api/auth/logout'); } finally { qc.clear(); navigate('/'); window.location.reload(); } };
  return (
    <div style={{ position: 'relative' }}>
      <button className="icon-btn" aria-label="Your account" aria-expanded={open} onClick={() => setOpen(!open)}>{initials(me.user?.name)}</button>
      {open && (
        <div className="jump" style={{ left: 'auto', right: 0, width: 220 }} onMouseLeave={() => setOpen(false)}>
          <div className="jump-head">{me.user?.name}<br /><span className="small">{me.user?.email}</span></div>
          <button className="jump-item" onClick={() => { setOpen(false); navigate('/profile'); }}>Profile & look</button>
          <button className="jump-item" onClick={() => { setOpen(false); navigate('/settings/my_security'); }}>My sign-in & 2FA</button>
          <button className="jump-item" onClick={signOut}>Sign out</button>
        </div>
      )}
    </div>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const { me } = useAuth();
  const can = useCan();
  const [newOpen, setNewOpen] = useState(false);
  const [menu, setMenu] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => setMenu(false), [pathname]);
  const counts = useQuery({ queryKey: ['ticket-counts'], enabled: can('tickets'), queryFn: () => api.get('/api/tickets?limit=1'), refetchInterval: 60_000 });
  const look = me.user?.look ?? 'indigo';
  return (
    <div className="app">
      {look === 'graphite' ? <Rail open={menu} /> : <Sidebar open={menu} openCount={counts.data?.counts?.open} />}
      <div className="main">
        <header className="topbar">
          <button className="btn menu-btn" aria-controls="main-nav" aria-expanded={menu} onClick={() => setMenu(!menu)}>{menu ? 'Close menu' : 'Menu'}</button>
          <JumpSearch />
          <div className="spacer" />
          <ClockButton />
          {can('tickets', 'edit') && <button className="btn primary" onClick={() => setNewOpen(true)}><Icon name="plus" size={16} />New ticket</button>}
          <UserMenu />
        </header>
        <main id="content">{children}</main>
      </div>
      {newOpen && <NewTicketDialog onClose={() => setNewOpen(false)} />}
    </div>
  );
}
