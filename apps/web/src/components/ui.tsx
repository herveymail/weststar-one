import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { Icon } from './Icon';
import { ApiError } from '../lib/api';

// ── Toasts ──
const ToastCtx = createContext<(msg: string, kind?: 'ok' | 'err') => void>(() => {});
export function ToastProvider({ children }: { children: ReactNode }) {
  const [t, setT] = useState<{ msg: string; kind: 'ok' | 'err' } | null>(null);
  const timer = useRef<number>(0);
  const show = useCallback((msg: string, kind: 'ok' | 'err' = 'ok') => {
    setT({ msg, kind }); window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setT(null), kind === 'err' ? 5000 : 2600);
  }, []);
  return <ToastCtx.Provider value={show}>{children}{t && <div role="status" className={`toast ${t.kind === 'err' ? 'err' : ''}`}>{t.msg}</div>}</ToastCtx.Provider>;
}
export const useToast = () => useContext(ToastCtx);
export const errMsg = (e: unknown) => (e instanceof ApiError ? (e.details?.length ? `${e.message} ${e.details.map((d) => d.message).join(' ')}` : e.message) : 'Something went wrong.');

// ── Drawer & dialog ──
function useEscape(onClose: () => void) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);
}

export function Drawer({ title, onClose, children, footer }: { title: ReactNode; onClose: () => void; children: ReactNode; footer?: ReactNode }) {
  useEscape(onClose);
  return (
    <div className="shade" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <section className="drawer" role="dialog" aria-modal="true" aria-label={typeof title === 'string' ? title : undefined}>
        <div className="drawer-head"><h2 style={{ flex: 1, minWidth: 0 }}>{title}</h2><button className="icon-btn" aria-label="Close" onClick={onClose}><Icon name="close" size={16} /></button></div>
        <div className="drawer-body">{children}</div>
        {footer && <div className="drawer-foot">{footer}</div>}
      </section>
    </div>
  );
}

export function Dialog({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEscape(onClose);
  return (
    <div className="shade center" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <section className="dialog" role="dialog" aria-modal="true" aria-label={title}><h2>{title}</h2>{children}</section>
    </div>
  );
}

// ── Pills ──
export function tone(v: unknown): string {
  const x = String(v ?? '').toLowerCase();
  if (/(overdue|failed|critical|offline|expired|breach|terminated|denied|lost|void)/.test(x)) return 'bad';
  if (/^(paid|active|valid|ok|success|accepted|signed|complete|approved|matched|current|won|renewed|portal)$/.test(x)) return 'good';
  if (/(pending|draft|sent|viewed|expiring|planning|in progress|paused|review|unmatched|not started|proposal|negotiation|waiting|warning|on hold|partial|upcoming|onboarding|submitted|scheduled|unread)/.test(x)) return 'warn';
  if (/^(new|open|contacted|qualified|running)$/.test(x)) return 'info';
  return '';
}
export const Pill = ({ v, cls }: { v: ReactNode; cls?: string }) => <span className={`pill ${cls ?? tone(v)}`}>{v}</span>;
export const prioClass = (p: string) => ({ Critical: 'crit', High: 'high', Medium: 'med', Low: '' } as Record<string, string>)[p] ?? '';
export const statusClass = (s: string) => (s === 'New' ? 'med' : s === 'Open' ? 'accent' : /Waiting/.test(s) ? 'high' : s === 'Scheduled' ? 'med' : '');

export function Later({ what }: { what: string }) {
  return <div className="later"><b style={{ display: 'block', color: 'var(--text)', fontSize: 15, marginBottom: 4 }}>{what}</b>This part is planned for a later round. Everything else on this page works.</div>;
}
