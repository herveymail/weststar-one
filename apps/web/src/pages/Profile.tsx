import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { errMsg, useToast } from '../components/ui';

export function Profile() {
  const { me, refresh } = useAuth();
  const toast = useToast();
  const [f, setF] = useState({ name: me.user?.name ?? '', title: me.user?.title ?? '', phone: me.user?.phone ?? '' });
  const save = async (patch: Record<string, unknown>, msg: string) => {
    try { await api.patch('/api/auth/profile', patch); toast(msg); await refresh(); } catch (e) { toast(errMsg(e), 'err'); }
  };
  const look = me.user?.look ?? 'indigo';
  return (
    <div className="page" style={{ maxWidth: 820 }}>
      <div className="page-head"><div className="titles"><div className="eyebrow">Your account</div><h1>Profile & look</h1></div></div>
      <section className="card pad" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <h2>Look</h2>
        <p className="desc" style={{ margin: 0 }}>Pick how Weststar ONE looks for you. It only changes your screen.</p>
        <div className="tiles" role="radiogroup" aria-label="Look">
          {([['indigo', 'Look 1 · Indigo Clean', 'Light, full sidebar with every section'], ['graphite', 'Look 2 · Graphite', 'Dark, slim icon bar with pop-out sections']] as const).map(([k, t, d]) => (
            <button key={k} role="radio" aria-checked={look === k} className="tile" style={{ textAlign: 'left', cursor: 'pointer', outline: look === k ? '2px solid var(--accent)' : undefined }} onClick={() => save({ look: k }, `Switched to ${t}.`)}>
              <span className="strong">{t}</span><span className="small muted">{d}</span>
            </button>
          ))}
        </div>
      </section>
      <section className="card pad" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <h2>Details</h2>
        <form className="form-grid" onSubmit={(e) => { e.preventDefault(); save({ name: f.name, title: f.title || null, phone: f.phone || null }, 'Profile saved.'); }}>
          <div className="field"><label htmlFor="p-n">Name</label><input id="p-n" className="input" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
          <div className="field"><label htmlFor="p-t">Title</label><input id="p-t" className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></div>
          <div className="field"><label htmlFor="p-p">Phone</label><input id="p-p" className="input" type="tel" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></div>
          <div className="field"><span className="label">Email</span><div>{me.user?.email}</div><span className="help">Ask an admin to change your email.</span></div>
          <div><button className="btn primary">Save</button></div>
        </form>
      </section>
      <p><Link to="/settings/my_security">Password, two-factor and sessions →</Link></p>
    </div>
  );
}
