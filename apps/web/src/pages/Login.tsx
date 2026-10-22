import { useState } from 'react';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { errMsg } from '../components/ui';

/** Sign in → (two-factor code) → (choose a new password) → (set up two-factor). Every gate the API enforces has a screen. */
export function Gate() {
  const { me, refresh } = useAuth();
  if (!me.user) return <SignIn onDone={refresh} />;
  if (!me.mfaPassed) return <MfaCode onDone={refresh} />;
  if (me.user.must_change_password) return <ForcedPassword onDone={refresh} />;
  if (me.mfaSetupRequired) return <Frame title="Set up two-factor sign-in" sub="Your account needs a code from an authenticator app every time you sign in."><MfaSetup onDone={refresh} /></Frame>;
  return null;
}

function Frame({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className="login-wrap">
      <div className="login">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}><span className="logo">W</span><b style={{ fontSize: 18 }}>Weststar ONE</b></div>
        <div className="card">
          <div><h1 style={{ fontSize: 22 }}>{title}</h1>{sub && <p className="desc">{sub}</p>}</div>
          {children}
        </div>
      </div>
    </div>
  );
}

function SignIn({ onDone }: { onDone: () => void }) {
  const [email, setEmail] = useState(''); const [password, setPassword] = useState('');
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr('');
    try { await api.post('/api/auth/login', { email, password }); onDone(); } catch (x) { setErr(errMsg(x)); } finally { setBusy(false); }
  };
  return (
    <Frame title="Sign in">
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {err && <div className="banner" role="alert">{err}</div>}
        <div className="field"><label htmlFor="email">Email</label><input id="email" className="input" type="email" autoComplete="username" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} /></div>
        <div className="field"><label htmlFor="pw">Password</label><input id="pw" className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></div>
        <button className="btn primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <p className="small muted" style={{ margin: 0 }}>Forgot your password? Ask an admin to reset it in Settings › Staff users.</p>
      </form>
    </Frame>
  );
}

function MfaCode({ onDone }: { onDone: () => void }) {
  const [code, setCode] = useState(''); const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr('');
    try { await api.post('/api/auth/mfa', { code }); onDone(); } catch (x) { setErr(errMsg(x)); setCode(''); } finally { setBusy(false); }
  };
  const cancel = async () => { await api.post('/api/auth/logout').catch(() => {}); onDone(); };
  return (
    <Frame title="Enter your code" sub="Open your authenticator app and type the 6-digit code for Weststar ONE. No phone? Use one of your recovery codes.">
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {err && <div className="banner" role="alert">{err}</div>}
        <div className="field"><label htmlFor="code">Code</label><input id="code" className="input num" inputMode="numeric" autoComplete="one-time-code" autoFocus required maxLength={20} value={code} onChange={(e) => setCode(e.target.value)} style={{ fontSize: 20, letterSpacing: '.2em' }} /></div>
        <button className="btn primary" disabled={busy || code.trim().length < 6}>{busy ? 'Checking…' : 'Continue'}</button>
        <button type="button" className="link-btn" onClick={cancel}>Use a different account</button>
      </form>
    </Frame>
  );
}

function ForcedPassword({ onDone }: { onDone: () => void }) {
  const [current, setCurrent] = useState(''); const [next, setNext] = useState(''); const [again, setAgain] = useState('');
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr('');
    if (next !== again) { setErr('The two new passwords do not match.'); return; }
    setBusy(true);
    try { await api.post('/api/auth/password', { current, next }); onDone(); } catch (x) { setErr(errMsg(x)); } finally { setBusy(false); }
  };
  return (
    <Frame title="Choose a new password" sub="Use at least 12 characters. A short sentence works well.">
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {err && <div className="banner" role="alert">{err}</div>}
        <div className="field"><label htmlFor="cur">Current (temporary) password</label><input id="cur" className="input" type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} /></div>
        <div className="field"><label htmlFor="new">New password</label><input id="new" className="input" type="password" autoComplete="new-password" minLength={12} required value={next} onChange={(e) => setNext(e.target.value)} /></div>
        <div className="field"><label htmlFor="new2">New password again</label><input id="new2" className="input" type="password" autoComplete="new-password" minLength={12} required value={again} onChange={(e) => setAgain(e.target.value)} /></div>
        <button className="btn primary" disabled={busy}>Save password</button>
      </form>
    </Frame>
  );
}

export function MfaSetup({ onDone }: { onDone: () => void }) {
  const [setup, setSetup] = useState<{ qr: string; secret: string } | null>(null);
  const [code, setCode] = useState(''); const [codes, setCodes] = useState<string[] | null>(null);
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  const start = async () => { setErr(''); try { setSetup(await api.post('/api/auth/mfa/setup')); } catch (x) { setErr(errMsg(x)); } };
  const confirm = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr('');
    try { const r = await api.post('/api/auth/mfa/enable', { code }); setCodes(r.recoveryCodes); } catch (x) { setErr(errMsg(x)); } finally { setBusy(false); }
  };
  if (codes) return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div className="banner info">Two-factor sign-in is on.</div>
      <p style={{ margin: 0 }}>Save these recovery codes somewhere safe, like your password manager. Each one works once if you lose your phone. They won't be shown again.</p>
      <div className="codes">{codes.map((c) => <span key={c}>{c}</span>)}</div>
      <button className="btn" onClick={() => navigator.clipboard?.writeText(codes.join('\n')).catch(() => {})}>Copy codes</button>
      <button className="btn primary" onClick={onDone}>I saved them, continue</button>
    </div>
  );
  if (!setup) return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {err && <div className="banner">{err}</div>}
      <p style={{ margin: 0 }}>You'll need an authenticator app such as Microsoft Authenticator, Google Authenticator, 1Password or Bitwarden.</p>
      <button className="btn primary" onClick={start}>Start setup</button>
    </div>
  );
  return (
    <form onSubmit={confirm} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {err && <div className="banner" role="alert">{err}</div>}
      <p style={{ margin: 0 }}>1. Scan this code with your authenticator app.</p>
      <img className="qr" src={setup.qr} alt="QR code to add Weststar ONE to your authenticator app" />
      <p className="small muted" style={{ margin: 0 }}>Can't scan? Enter this key instead: <span className="code">{setup.secret.match(/.{1,4}/g)?.join(' ')}</span></p>
      <div className="field"><label htmlFor="c1">2. Type the 6-digit code it shows</label><input id="c1" className="input num" inputMode="numeric" autoComplete="one-time-code" required maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} /></div>
      <button className="btn primary" disabled={busy || code.length < 6}>Turn on two-factor</button>
    </form>
  );
}
