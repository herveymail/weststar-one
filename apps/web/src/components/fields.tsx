import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { Field } from '@ws/shared';
import { api, qs } from '../lib/api';
import { Icon } from './Icon';
import { errMsg, useToast } from './ui';

/** Searchable picker for a reference field (client, user, vendor …). */
export function RefPicker({ id, refRes, value, label, onChange, filter, required }: {
  id: string; refRes: string; value: number | null; label?: string; onChange: (v: number | null, label?: string) => void;
  filter?: Record<string, unknown>; required?: boolean;
}) {
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [shown, setShown] = useState(label ?? '');
  useEffect(() => { setShown(label ?? ''); }, [label]);
  const opts = useQuery({
    queryKey: ['options', refRes, q, filter], enabled: open,
    queryFn: () => api.get<{ id: number; label: string }[]>(`/api/options/${refRes}${qs({ q, ...(filter ?? {}) })}`),
  });
  const box = useRef<HTMLDivElement>(null);
  return (
    <div ref={box} style={{ position: 'relative' }} onBlur={(e) => { if (!box.current?.contains(e.relatedTarget as Node)) setOpen(false); }}>
      <div style={{ display: 'flex', gap: 6 }}>
        <input id={id} className="input" autoComplete="off" required={required && !value} placeholder="Search…" value={open ? q : shown}
          onFocus={() => { setOpen(true); setQ(''); }} onChange={(e) => setQ(e.target.value)} />
        {value && !required ? <button type="button" className="btn small" aria-label="Clear" onClick={() => { onChange(null, ''); setShown(''); }}>✕</button> : null}
      </div>
      {open && (
        <div className="jump" role="listbox" style={{ maxHeight: 260, overflowY: 'auto' }}>
          {opts.isLoading && <div className="jump-head">Loading…</div>}
          {(opts.data ?? []).map((o) => (
            <button type="button" key={o.id} role="option" aria-selected={o.id === value} className={`jump-item ${o.id === value ? 'active' : ''}`}
              onClick={() => { onChange(o.id, o.label); setShown(o.label); setOpen(false); }}>{o.label || `#${o.id}`}</button>
          ))}
          {opts.data && opts.data.length === 0 && <div className="jump-head">No matches</div>}
        </div>
      )}
    </div>
  );
}

/** Encrypted field: shows whether a value is saved, lets permitted users reveal it, and accepts a replacement. */
export function SecretInput({ id, res, rowId, field, isSet, value, onChange }: { id: string; res: string; rowId?: number; field: Field; isSet: boolean; value: string; onChange: (v: string) => void }) {
  const toast = useToast();
  const [revealed, setRevealed] = useState<string | null>(null);
  const reveal = async () => {
    try { const r = await api.post(`/api/r/${res}/${rowId}/reveal/${field.key}`); setRevealed(r.value); }
    catch (e) { toast(errMsg(e), 'err'); }
  };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {isSet && rowId && (
        <div className="secret-row">
          <Icon name="lock" size={16} />
          {revealed !== null ? <span className="code">{revealed || '(empty)'}</span> : <span className="muted">Saved and encrypted</span>}
          {revealed === null ? <button type="button" className="link-btn" onClick={reveal}><Icon name="eye" size={14} />Show</button> : <button type="button" className="link-btn" onClick={() => setRevealed(null)}>Hide</button>}
        </div>
      )}
      <input id={id} className="input" type="password" autoComplete="new-password" placeholder={isSet ? 'Type to replace' : 'Not set'} value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

export function FieldInput({ f, id, value, onChange, labels, res, rowId, row }: {
  f: Field; id: string; value: any; onChange: (v: any, label?: string) => void; labels?: Record<string, Record<number, string>>;
  res: string; rowId?: number; row?: Record<string, any>;
}) {
  switch (f.type) {
    case 'textarea': return <textarea id={id} className="textarea" value={value ?? ''} onChange={(e) => onChange(e.target.value)} maxLength={20000} />;
    case 'select': return (
      <select id={id} className="select" value={value ?? ''} required={f.required} onChange={(e) => onChange(e.target.value)}>
        {!f.required && <option value="">—</option>}
        {f.options!.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
    case 'bool': return <label className="check"><input id={id} type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />{f.label}</label>;
    case 'int': return <input id={id} className="input num" type="number" step="1" value={value ?? ''} required={f.required} onChange={(e) => onChange(e.target.value)} />;
    case 'decimal': case 'money': return <input id={id} className="input num" type="number" step="0.01" inputMode="decimal" value={value ?? ''} required={f.required} onChange={(e) => onChange(e.target.value)} />;
    case 'date': return <input id={id} className="input" type="date" value={value ?? ''} required={f.required} onChange={(e) => onChange(e.target.value)} />;
    case 'datetime': return <input id={id} className="input" type="datetime-local" value={toLocalInput(value)} required={f.required} onChange={(e) => onChange(e.target.value ? new Date(e.target.value).toISOString() : '')} />;
    case 'email': return <input id={id} className="input" type="email" value={value ?? ''} required={f.required} onChange={(e) => onChange(e.target.value)} />;
    case 'phone': return <input id={id} className="input" type="tel" value={value ?? ''} required={f.required} onChange={(e) => onChange(e.target.value)} />;
    case 'url': return <input id={id} className="input" type="url" placeholder="https://" value={value ?? ''} required={f.required} onChange={(e) => onChange(e.target.value)} />;
    case 'ref': return <RefPicker id={id} refRes={f.ref!} value={value ?? null} required={f.required} label={value ? labels?.[f.key]?.[value] : ''} onChange={onChange} />;
    case 'secret': return <SecretInput id={id} res={res} rowId={rowId} field={f} isSet={!!row?.[`${f.key}__set`]} value={value ?? ''} onChange={onChange} />;
    default: return <input id={id} className="input" value={value ?? ''} required={f.required} maxLength={f.max ?? 500} onChange={(e) => onChange(e.target.value)} />;
  }
}

function toLocalInput(v: unknown) {
  if (!v) return '';
  const d = new Date(String(v));
  if (Number.isNaN(d.getTime())) return '';
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}
