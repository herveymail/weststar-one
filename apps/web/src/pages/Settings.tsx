import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ROLES, SETTINGS, type SettingField, type SettingPage } from '@ws/shared';
import { api, ago, fmtDateTime, qs } from '../lib/api';
import { useAuth, useCan } from '../lib/auth';
import { Dialog, Pill, errMsg, useToast } from '../components/ui';
import { Icon } from '../components/Icon';
import { MfaSetup } from './Login';

const allPages = SETTINGS.flatMap((g) => g.items.map((i) => ({ ...i, group: g.title })));
const Back = () => <Link to="/settings" className="link-btn"><Icon name="back" size={16} />Settings</Link>;

export function SettingsHome() {
  const [q, setQ] = useState('');
  const can = useCan();
  const term = q.trim().toLowerCase();
  const groups = SETTINGS.map((g) => ({ ...g, items: g.items.filter((i) => (i.id === 'my_security' || can('admin')) && (!term || (g.title + i.title + i.desc + (i.fields ?? []).map((f) => f.label).join(' ')).toLowerCase().includes(term))) })).filter((g) => g.items.length);
  return (
    <div className="page">
      <div className="page-head">
        <div className="titles"><div className="eyebrow">Admin</div><h1>Settings</h1><p className="desc">Every setting in one place. Search finds a setting by what it does.</p></div>
        <div style={{ flex: '0 1 320px' }}><label htmlFor="sq" className="sr">Search settings</label><input id="sq" className="input" placeholder="Search settings (e.g. SLA, logo, MFA)" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      </div>
      {groups.map((g) => (
        <section key={g.id} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div><h2 style={{ fontSize: 16 }}>{g.title}</h2><div className="small muted">{g.desc}</div></div>
          <div className="tiles">{g.items.map((i) => <Link key={i.id} to={`/settings/${i.id}`} className="tile"><span className="strong">{i.title}</span><span className="small muted">{i.desc}</span></Link>)}</div>
        </section>
      ))}
      {groups.length === 0 && <div className="empty">No setting matches “{q}”.</div>}
    </div>
  );
}

export function SettingsPageView() {
  const { page } = useParams();
  const p = allPages.find((x) => x.id === page);
  if (!p) return <div className="page"><Back /><p className="banner">That settings page does not exist.</p></div>;
  const body = p.page === 'users' ? <UsersAdmin /> : p.page === 'my-security' ? <MySecurity /> : p.page === 'audit' ? <AuditLog /> : p.page === 'security-log' ? <SecurityLog />
    : p.page === 'jobs' ? <Jobs /> : p.page === 'import' ? <ImportHelp /> : <SettingsForm p={p} />;
  return (
    <div className="page">
      <div className="page-head"><div className="titles"><Back /><h1>{p.title}</h1><p className="desc">{p.desc}</p></div></div>
      {body}
    </div>
  );
}

function SettingsForm({ p }: { p: SettingPage }) {
  const toast = useToast(); const can = useCan(); const qc = useQueryClient();
  const s = useQuery({ queryKey: ['settings'], queryFn: () => api.get('/api/settings') });
  const [vals, setVals] = useState<Record<string, string>>({});
  useEffect(() => { if (s.data) setVals(Object.fromEntries((p.fields ?? []).map((f) => [f.key, typeof s.data[f.key] === 'string' ? s.data[f.key] : '']))); }, [s.data, p]);
  if (s.isError) return <p className="banner">{errMsg(s.error)}</p>;
  if (!s.data) return <p className="muted">Loading…</p>;
  const save = async () => {
    try { await api.put('/api/settings', vals); toast('Settings saved.'); qc.invalidateQueries({ queryKey: ['settings'] }); qc.invalidateQueries({ queryKey: ['me'] }); }
    catch (e) { toast(errMsg(e), 'err'); }
  };
  const input = (f: SettingField) => {
    const id = 'set-' + f.key;
    const v = vals[f.key] ?? '';
    const on = (x: string) => setVals((o) => ({ ...o, [f.key]: x }));
    if (f.type === 'textarea') return <textarea id={id} className="textarea" value={v} onChange={(e) => on(e.target.value)} />;
    if (f.type === 'bool') return <label className="check"><input id={id} type="checkbox" checked={v === 'true'} onChange={(e) => on(e.target.checked ? 'true' : 'false')} />On</label>;
    if (f.type === 'select') return <select id={id} className="select" value={v} onChange={(e) => on(e.target.value)}><option value="">Default</option>{f.options!.map((o) => <option key={o}>{o}</option>)}</select>;
    if (f.type === 'secret') return <input id={id} className="input" type="password" autoComplete="new-password" placeholder={s.data[f.key]?.set ? 'Saved — type to replace' : 'Not set'} value={v} onChange={(e) => on(e.target.value)} />;
    return <input id={id} className="input" type={f.type === 'int' ? 'number' : 'text'} value={v} onChange={(e) => on(e.target.value)} />;
  };
  return (
    <section className="card pad" style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 760 }}>
      <form className="form-grid" onSubmit={(e) => { e.preventDefault(); save(); }}>
        {(p.fields ?? []).map((f) => (
          <div key={f.key} className={`field ${f.type === 'textarea' ? 'wide' : ''}`}>
            <label htmlFor={'set-' + f.key}>{f.label}{f.type === 'secret' && <> <Icon name="lock" size={12} /></>}</label>
            {input(f)}{f.help && <span className="help">{f.help}</span>}
          </div>
        ))}
        <button type="submit" hidden />
      </form>
      {can('admin', 'manage') ? <div><button className="btn primary" onClick={save}>Save</button></div> : <p className="small muted">You can view these settings. Only admins can change them.</p>}
      {(p.fields ?? []).some((f) => f.type === 'secret') && <p className="small muted" style={{ margin: 0 }}>Fields with a lock are stored encrypted and are never shown again after saving.</p>}
    </section>
  );
}

function UsersAdmin() {
  const toast = useToast(); const qc = useQueryClient(); const { me } = useAuth(); const can = useCan();
  const list = useQuery({ queryKey: ['users'], queryFn: () => api.get('/api/users') });
  const [edit, setEdit] = useState<any | null>(null);
  const act = async (u: any, action: string, body?: any) => {
    try { await api.post(`/api/users/${u.id}/${action}`, body); toast('Done.'); qc.invalidateQueries({ queryKey: ['users'] }); }
    catch (e) { toast(errMsg(e), 'err'); }
  };
  const resetPw = (u: any) => {
    const pw = Array.from(crypto.getRandomValues(new Uint8Array(12))).map((b) => 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'[b % 56]).join('');
    act(u, 'reset-password', { password: pw }).then(() => setEdit({ ...u, tempPassword: pw, showTemp: true }));
  };
  return (
    <>
      {can('admin', 'manage') && <div><button className="btn primary" onClick={() => setEdit({ role: 'tech', hr_access: false })}><Icon name="plus" size={16} />Add user</button></div>}
      <section className="card" style={{ overflow: 'hidden' }}>
        <div className="table-wrap"><table className="grid">
          <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>H/R</th><th>2FA</th><th>Last sign-in</th><th>Status</th></tr></thead>
          <tbody>{(list.data ?? []).map((u: any) => (
            <tr key={u.id} onClick={() => setEdit(u)}>
              <td className="strong">{u.name}{u.id === me.user?.id && <span className="small muted"> (you)</span>}</td><td>{u.email}</td><td>{u.role}</td>
              <td>{u.hr_access ? 'Yes' : '—'}</td><td>{u.mfa_enabled ? <Pill v="On" cls="good" /> : <Pill v="Off" cls="warn" />}</td>
              <td className="small muted">{u.last_login_at ? ago(u.last_login_at) : 'Never'}</td>
              <td>{u.archived ? <Pill v="Archived" cls="bad" /> : u.locked ? <Pill v="Locked" cls="bad" /> : u.must_change_password ? <Pill v="Must change password" cls="warn" /> : <Pill v="Active" cls="good" />}</td>
            </tr>
          ))}</tbody>
        </table></div>
      </section>
      {edit && <UserDialog u={edit} onClose={() => setEdit(null)} onAction={(a) => (a === 'reset-password' ? resetPw(edit) : act(edit, a).then(() => setEdit(null)))} />}
    </>
  );
}

function UserDialog({ u, onClose, onAction }: { u: any; onClose: () => void; onAction: (a: string) => void }) {
  const toast = useToast(); const qc = useQueryClient(); const can = useCan();
  const [f, setF] = useState({ name: u.name ?? '', email: u.email ?? '', role: u.role ?? 'tech', hr_access: !!u.hr_access, title: u.title ?? '' });
  const [pw, setPw] = useState(() => Array.from(crypto.getRandomValues(new Uint8Array(12))).map((b) => 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'[b % 56]).join(''));
  const isNew = !u.id;
  const save = async () => {
    try {
      if (isNew) await api.post('/api/users', { ...f, title: f.title || null, password: pw });
      else await api.patch(`/api/users/${u.id}`, { ...f, title: f.title || null });
      toast(isNew ? 'User added. Give them the temporary password.' : 'Saved.'); qc.invalidateQueries({ queryKey: ['users'] });
      if (!isNew) onClose();
    } catch (e) { toast(errMsg(e), 'err'); }
  };
  const manage = can('admin', 'manage');
  return (
    <Dialog title={isNew ? 'Add user' : u.name} onClose={onClose}>
      {u.showTemp && <div className="banner info">New temporary password: <span className="code">{u.tempPassword}</span> — they must change it when they sign in.</div>}
      <div className="form-grid">
        <div className="field"><label htmlFor="u-n">Name</label><input id="u-n" className="input" value={f.name} disabled={!manage} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
        <div className="field"><label htmlFor="u-e">Email</label><input id="u-e" className="input" type="email" value={f.email} disabled={!manage} onChange={(e) => setF({ ...f, email: e.target.value })} /></div>
        <div className="field"><label htmlFor="u-r">Role</label><select id="u-r" className="select" value={f.role} disabled={!manage} onChange={(e) => setF({ ...f, role: e.target.value })}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select></div>
        <div className="field"><label htmlFor="u-t">Title</label><input id="u-t" className="input" value={f.title} disabled={!manage} onChange={(e) => setF({ ...f, title: e.target.value })} /></div>
        <label className="check"><input type="checkbox" checked={f.hr_access} disabled={!manage} onChange={(e) => setF({ ...f, hr_access: e.target.checked })} />H/R access</label>
      </div>
      {isNew && <div className="field"><label htmlFor="u-p">Temporary password</label><input id="u-p" className="input code" value={pw} onChange={(e) => setPw(e.target.value)} /><span className="help">They must choose their own password at first sign-in.</span></div>}
      <p className="small muted" style={{ margin: 0 }}>Admins: everything. Managers: everything except H/R and changing settings. Techs: tickets, clients, projects, tools. Viewers: read only. H/R access is a separate switch.</p>
      {manage && <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}><button className="btn primary" onClick={save}>{isNew ? 'Add user' : 'Save'}</button><button className="btn" onClick={onClose}>Close</button></div>}
      {!isNew && manage && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, borderTop: '1px solid var(--line)', paddingTop: 14 }}>
          <button className="btn small" onClick={() => onAction('reset-password')}>Reset password</button>
          {u.mfa_enabled && <button className="btn small" onClick={() => onAction('reset-mfa')}>Reset 2FA</button>}
          {u.locked && <button className="btn small" onClick={() => onAction('unlock')}>Unlock</button>}
          <button className="btn small" onClick={() => onAction('sign-out')}>Sign out everywhere</button>
          {u.archived ? <button className="btn small" onClick={() => onAction('restore')}>Restore</button> : <button className="btn small danger" onClick={() => onAction('archive')}>Archive user</button>}
        </div>
      )}
    </Dialog>
  );
}

function MySecurity() {
  const { me, refresh } = useAuth(); const toast = useToast(); const qc = useQueryClient();
  const sessions = useQuery({ queryKey: ['sessions'], queryFn: () => api.get('/api/auth/sessions') });
  const [pw, setPw] = useState({ current: '', next: '' });
  const [setup, setSetup] = useState(false);
  const [disable, setDisable] = useState('');
  const changePw = async () => { try { await api.post('/api/auth/password', pw); setPw({ current: '', next: '' }); toast('Password changed. Your other sessions were signed out.'); qc.invalidateQueries({ queryKey: ['sessions'] }); } catch (e) { toast(errMsg(e), 'err'); } };
  const off = async () => { try { await api.post('/api/auth/mfa/disable', { password: disable }); setDisable(''); toast('Two-factor turned off.'); refresh(); } catch (e) { toast(errMsg(e), 'err'); } };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 760 }}>
      <section className="card pad" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <h2>Two-factor sign-in {me.user?.mfa_enabled ? <Pill v="On" cls="good" /> : <Pill v="Off" cls="warn" />}</h2>
        {!me.user?.mfa_enabled && (setup ? <MfaSetup onDone={() => { setSetup(false); refresh(); }} /> : <div><button className="btn primary" onClick={() => setSetup(true)}>Turn on two-factor</button></div>)}
        {me.user?.mfa_enabled && (
          <form onSubmit={(e) => { e.preventDefault(); off(); }} style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'flex-end' }}>
            <div className="field" style={{ flex: '1 1 220px' }}><label htmlFor="dpw">To turn it off, enter your password</label><input id="dpw" className="input" type="password" autoComplete="current-password" value={disable} onChange={(e) => setDisable(e.target.value)} /></div>
            <button className="btn danger" disabled={!disable}>Turn off</button>
          </form>
        )}
      </section>
      <section className="card pad" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <h2>Change password</h2>
        <form className="form-grid" onSubmit={(e) => { e.preventDefault(); changePw(); }}>
          <div className="field"><label htmlFor="cp1">Current password</label><input id="cp1" className="input" type="password" autoComplete="current-password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} /></div>
          <div className="field"><label htmlFor="cp2">New password (12+ characters)</label><input id="cp2" className="input" type="password" autoComplete="new-password" minLength={12} value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} /></div>
          <div><button className="btn primary" disabled={!pw.current || pw.next.length < 12}>Change password</button></div>
        </form>
      </section>
      <section className="card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '16px 18px 8px' }}><h2>Where you're signed in</h2></div>
        <div className="table-wrap"><table className="grid"><tbody>
          {(sessions.data ?? []).map((s: any) => (
            <tr key={s.id} style={{ cursor: 'default' }}>
              <td><div className="strong">{s.user_agent?.slice(0, 80) || 'Unknown browser'}</div><div className="small muted">{s.ip} · signed in {fmtDateTime(s.created_at)} · active {ago(s.last_seen_at)}</div></td>
              <td style={{ textAlign: 'right' }}>{s.current ? <Pill v="This device" cls="good" /> : <button className="btn small" onClick={async () => { await api.del(`/api/auth/sessions/${s.id}`).catch(() => {}); qc.invalidateQueries({ queryKey: ['sessions'] }); }}>Sign out</button>}</td>
            </tr>
          ))}
        </tbody></table></div>
      </section>
    </div>
  );
}

function AuditLog() {
  const [q, setQ] = useState('');
  const l = useQuery({ queryKey: ['audit', q], queryFn: () => api.get(`/api/audit${qs({ q })}`) });
  return (
    <>
      <div style={{ maxWidth: 360 }}><label htmlFor="aq" className="sr">Search the audit log</label><input id="aq" className="input" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      <section className="card" style={{ overflow: 'hidden' }}><div className="table-wrap"><table className="grid">
        <thead><tr><th>When</th><th>Who</th><th>What</th><th>Details</th><th>IP</th></tr></thead>
        <tbody>{(l.data ?? []).map((a: any) => (
          <tr key={a.id} style={{ cursor: 'default' }}>
            <td className="small num" style={{ whiteSpace: 'nowrap' }}>{fmtDateTime(a.created_at)}</td><td>{a.user_name ?? <span className="muted">system</span>}</td>
            <td><span className="code">{a.action}</span> <span className="small muted">{a.entity}</span></td><td>{a.summary}</td><td className="small muted">{a.ip}</td>
          </tr>
        ))}</tbody>
      </table></div></section>
    </>
  );
}

function SecurityLog() {
  const l = useQuery({ queryKey: ['seclog'], queryFn: () => api.get('/api/security-log') });
  return (
    <section className="card" style={{ overflow: 'hidden' }}><div className="table-wrap"><table className="grid">
      <thead><tr><th>When</th><th>Email</th><th>IP</th><th>Result</th></tr></thead>
      <tbody>{(l.data ?? []).map((a: any) => (
        <tr key={a.id} style={{ cursor: 'default' }}><td className="small num">{fmtDateTime(a.created_at)}</td><td>{a.email}</td><td className="small">{a.ip}</td><td>{a.success ? <Pill v="Signed in" cls="good" /> : <Pill v={a.reason?.replace(/_/g, ' ') ?? 'failed'} cls="bad" />}</td></tr>
      ))}</tbody>
    </table></div></section>
  );
}

function Jobs() {
  const l = useQuery({ queryKey: ['jobs'], queryFn: () => api.get('/api/jobs') });
  return (
    <section className="card" style={{ overflow: 'hidden' }}><div className="table-wrap"><table className="grid">
      <thead><tr><th>Job</th><th>Schedule</th><th>Last run</th><th>Result</th></tr></thead>
      <tbody>{(l.data ?? []).map((j: any) => (
        <tr key={j.name} style={{ cursor: 'default' }}><td className="strong">{j.label}</td><td className="code">{j.cron}</td><td>{j.last ? ago(j.last.at) : <span className="muted">Not yet — is the worker running?</span>}</td><td className="small">{j.last ? JSON.stringify(j.last.result) : ''}</td></tr>
      ))}</tbody>
    </table></div></section>
  );
}

function ImportHelp() {
  const runs = useQuery({ queryKey: ['import-runs'], queryFn: () => api.get('/api/import-runs') });
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 860 }}>
      <section className="card pad" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <h2>How importing works</h2>
        <p style={{ margin: 0 }}>The import runs on the server from the command line, so database passwords and the old encryption keys never pass through a browser. Point it at the old app's <span className="code">config/config.php</span>; it reads the database login and both old keys from there.</p>
        <pre className="block">{`# 1) Practice run — shows counts, saves nothing
pnpm import:legacy --old-config /var/www/myflow/config/config.php --dry-run

# 2) Real import — safe to repeat; records are updated, never duplicated
pnpm import:legacy --old-config /var/www/myflow/config/config.php`}</pre>
        <p className="small muted" style={{ margin: 0 }}>Ticket, invoice and quote numbers stay the same. Old passwords keep working and two-factor keeps working. Wi-Fi passwords, ISP accounts and H/R fields are decrypted with the old keys and re-encrypted with the new one.</p>
      </section>
      <section className="card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '16px 18px 8px' }}><h2>Import history</h2></div>
        <div className="table-wrap"><table className="grid">
          <thead><tr><th>Started</th><th>Type</th><th>Records</th><th>Result</th></tr></thead>
          <tbody>{(runs.data ?? []).map((r: any) => {
            const total = (r.summary ?? []).reduce((a: number, s: any) => a + (s.imported ?? 0), 0);
            const warn = (r.summary ?? []).reduce((a: number, s: any) => a + (s.warnings?.length ?? 0), 0);
            return <tr key={r.id} style={{ cursor: 'default' }}><td className="small">{fmtDateTime(r.started_at)}</td><td>{r.dry_run ? 'Practice run' : 'Import'}</td><td className="num">{total}</td><td>{r.error ? <Pill v="Failed" cls="bad" /> : !r.finished_at ? <Pill v="Running" cls="warn" /> : warn ? <Pill v={`${warn} warnings`} cls="warn" /> : <Pill v="OK" cls="good" />}</td></tr>;
          })}</tbody>
        </table></div>
        {runs.data?.length === 0 && <div className="empty">No imports yet.</div>}
      </section>
    </div>
  );
}
