import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { RES, NAV, type Field, type Resource } from '@ws/shared';
import { api, fmtDate, fmtDateTime, money, qs, ApiError } from '../lib/api';
import { useCan } from '../lib/auth';
import { Drawer, Pill, errMsg, useToast } from './ui';
import { FieldInput } from './fields';
import { Icon } from './Icon';

export const groupOf = (r: Resource) => NAV.find((g) => g.items.some((i) => i.id === r.id || (i.id === 'marketing' && r.id === 'campaigns') || (i.id === 'hr' && r.id === 'employees')))?.group ?? null;

export function cellValue(f: Field, row: Record<string, any>, labels: Record<string, Record<number, string>>): ReactNode {
  const v = row[f.key];
  if (f.type === 'secret') return row[`${f.key}__set`] ? <span className="muted">●●●●</span> : <span className="muted">—</span>;
  if (v === null || v === undefined || v === '') return <span className="muted">—</span>;
  switch (f.type) {
    case 'money': return <span className="num">{money(v)}</span>;
    case 'decimal': case 'int': return <span className="num">{Number(v).toLocaleString()}</span>;
    case 'date': return fmtDate(v);
    case 'datetime': return fmtDateTime(v);
    case 'bool': return v ? 'Yes' : 'No';
    case 'ref': return labels[f.key]?.[v] ?? `#${v}`;
    case 'select': return f.key === 'status' || f.key === 'stage' || f.key.endsWith('_status') || f.key === 'last_result' || f.key === 'visibility' ? <Pill v={v} /> : String(v);
    case 'url': return <a href={String(v)} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>{String(v).replace(/^https?:\/\//, '')}</a>;
    default: return String(v);
  }
}

interface LineItem { description: string; qty: number | string; rate: number | string; taxable: boolean }

function LineItems({ items, onChange, taxRate }: { items: LineItem[]; onChange: (i: LineItem[]) => void; taxRate: number }) {
  const set = (i: number, patch: Partial<LineItem>) => onChange(items.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const sub = items.reduce((a, x) => a + Number(x.qty || 0) * Number(x.rate || 0), 0);
  const tax = items.reduce((a, x) => a + (x.taxable ? Number(x.qty || 0) * Number(x.rate || 0) : 0), 0) * (taxRate || 0) / 100;
  return (
    <div className="card" style={{ overflow: 'hidden' }}>
      <div className="table-wrap">
        <table className="grid">
          <thead><tr><th>Description</th><th style={{ width: 80 }}>Qty</th><th style={{ width: 110 }}>Rate</th><th style={{ width: 70 }}>Tax</th><th style={{ width: 100 }}>Total</th><th style={{ width: 40 }}><span className="sr">Remove</span></th></tr></thead>
          <tbody>
            {items.map((it, i) => (
              <tr key={i} style={{ cursor: 'default' }}>
                <td><label className="sr" htmlFor={`li-d-${i}`}>Description</label><input id={`li-d-${i}`} className="input" value={it.description} onChange={(e) => set(i, { description: e.target.value })} /></td>
                <td><label className="sr" htmlFor={`li-q-${i}`}>Qty</label><input id={`li-q-${i}`} className="input num" type="number" step="0.01" value={it.qty} onChange={(e) => set(i, { qty: e.target.value })} /></td>
                <td><label className="sr" htmlFor={`li-r-${i}`}>Rate</label><input id={`li-r-${i}`} className="input num" type="number" step="0.01" value={it.rate} onChange={(e) => set(i, { rate: e.target.value })} /></td>
                <td><label className="check" style={{ justifyContent: 'center' }}><input type="checkbox" checked={it.taxable} onChange={(e) => set(i, { taxable: e.target.checked })} /><span className="sr">Taxable</span></label></td>
                <td className="num">{money(Number(it.qty || 0) * Number(it.rate || 0))}</td>
                <td><button type="button" className="btn small" aria-label="Remove line" onClick={() => onChange(items.filter((_, j) => j !== i))}>✕</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pager">
        <button type="button" className="btn small" onClick={() => onChange([...items, { description: '', qty: 1, rate: 0, taxable: true }])}><Icon name="plus" size={14} />Add line</button>
        <div className="num" style={{ textAlign: 'right' }}>Subtotal {money(sub)} · Tax {money(tax)} · <b>Total {money(sub + tax)}</b></div>
      </div>
    </div>
  );
}

/** Create / edit drawer for any registry module. */
export function ResourceForm({ res, id, defaults, onClose, onSaved }: { res: string; id?: number; defaults?: Record<string, any>; onClose: () => void; onSaved?: (row: any) => void }) {
  const r = RES[res];
  const can = useCan();
  const toast = useToast();
  const qc = useQueryClient();
  const detail = useQuery({ queryKey: ['r', res, id], enabled: !!id, queryFn: () => api.get(`/api/r/${res}/${id}`) });
  const [data, setData] = useState<Record<string, any> | null>(id ? null : { ...Object.fromEntries(r.fields.filter((f) => f.default !== undefined).map((f) => [f.key, f.default])), ...(defaults ?? {}) });
  const [items, setItems] = useState<LineItem[] | null>(id ? null : []);
  const [labels, setLabels] = useState<Record<string, Record<number, string>>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!id || !detail.data || data !== null) return;
    const row = detail.data.row;
    setData(Object.fromEntries(r.fields.map((f) => [f.key, f.type === 'secret' ? '' : row[f.key]])));
    setLabels(detail.data.labels ?? {});
    if (r.lineItems) setItems((detail.data.items ?? []).map((x: any) => ({ description: x.description, qty: x.qty, rate: x.rate, taxable: x.taxable })));
  }, [id, detail.data, data, r]);
  const row = detail.data?.row;
  const editable = can(r.area, 'edit') || !!r.ownerScoped;
  const canArchive = can(r.area, 'manage');

  const save = async () => {
    if (!data) return;
    setSaving(true); setErrors({});
    const payload: Record<string, any> = {};
    for (const f of r.fields) {
      if (f.readOnly || !(f.key in data)) continue;
      if (f.type === 'secret' && !data[f.key]) continue;
      if (r.ownerScoped && f.key === 'user_id') continue;
      payload[f.key] = data[f.key] === undefined ? null : data[f.key];
    }
    try {
      const body: any = { data: payload };
      if (r.lineItems && items) body.items = items.filter((x) => x.description.trim()).map((x) => ({ description: x.description, qty: Number(x.qty || 0), rate: Number(x.rate || 0), taxable: x.taxable }));
      const out = id ? await api.patch(`/api/r/${res}/${id}`, body) : await api.post(`/api/r/${res}`, body);
      toast(id ? 'Saved.' : `${r.singular} created.`);
      qc.invalidateQueries({ queryKey: ['r', res] }); qc.invalidateQueries({ queryKey: ['list', res] });
      onSaved?.(out.row); onClose();
    } catch (e) {
      if (e instanceof ApiError && e.details) setErrors(Object.fromEntries(e.details.map((d) => [d.field.replace(/^data\./, ''), d.message])));
      toast(errMsg(e), 'err');
    } finally { setSaving(false); }
  };
  const archive = async () => {
    try { await api.del(`/api/r/${res}/${id}`); toast('Archived. You can restore it from the Archived view.'); qc.invalidateQueries({ queryKey: ['list', res] }); onClose(); }
    catch (e) { toast(errMsg(e), 'err'); }
  };
  const restore = async () => {
    try { await api.post(`/api/r/${res}/${id}/restore`); toast('Restored.'); qc.invalidateQueries({ queryKey: ['list', res] }); onClose(); }
    catch (e) { toast(errMsg(e), 'err'); }
  };

  const title = id ? (row ? `${r.singular} ${row.number ?? row.name ?? row.title ?? row.company ?? ''}`.trim() : r.singular) : `New ${r.singular.toLowerCase()}`;
  return (
    <Drawer title={title} onClose={onClose} footer={data && (
      <>
        {editable && !row?.archived_at && <button className="btn primary" disabled={saving} onClick={save}>{saving ? 'Saving…' : id ? 'Save changes' : `Create ${r.singular.toLowerCase()}`}</button>}
        <button className="btn" onClick={onClose}>Cancel</button>
        <div className="spacer" />
        {id && canArchive && !row?.archived_at && <button className="btn danger" onClick={archive}>Archive</button>}
        {id && canArchive && row?.archived_at && <button className="btn" onClick={restore}>Restore</button>}
      </>
    )}>
      {id && detail.isLoading && <p className="muted">Loading…</p>}
      {detail.isError && <p className="banner">{errMsg(detail.error)}</p>}
      {row?.archived_at && <p className="banner info">This record is archived.</p>}
      {data && (
        <form className="form-grid" onSubmit={(e) => { e.preventDefault(); save(); }}>
          {r.fields.filter((f) => !(r.ownerScoped && f.key === 'user_id' && !id)).map((f) => {
            const fid = `f-${res}-${f.key}`;
            const wide = f.type === 'textarea' || (f.type === 'secret' && f.key === 'body');
            if (f.readOnly) {
              if (!id) return null;
              return <div key={f.key} className="field"><span className="label">{f.label}</span><div>{cellValue(f, row ?? {}, labels)}</div></div>;
            }
            return (
              <div key={f.key} className={`field ${wide ? 'wide' : ''}`}>
                {f.type !== 'bool' && <label htmlFor={fid}>{f.label}{f.required ? ' *' : ''}</label>}
                <FieldInput f={f} id={fid} res={res} rowId={id} row={row} value={data[f.key]} labels={labels}
                  onChange={(v, label) => { setData((d) => ({ ...d!, [f.key]: v })); if (f.type === 'ref') setLabels((l) => ({ ...l, [f.key]: { ...(l[f.key] ?? {}), [v as number]: label ?? '' } })); }} />
                {f.help && <span className="help">{f.help}</span>}
                {errors[f.key] && <span className="err">{errors[f.key]}</span>}
              </div>
            );
          })}
          <button type="submit" hidden />
        </form>
      )}
      {r.lineItems && items && <><h3>Line items</h3><LineItems items={items} onChange={setItems} taxRate={Number(data?.tax_rate ?? 0)} /></>}
    </Drawer>
  );
}

/** List page (or embedded list) for any registry module. */
export function ResourceList({ res, filter, embedded, onOpen, title, newDefaults, extraActions }: {
  res: string; filter?: Record<string, unknown>; embedded?: boolean; onOpen?: (row: any) => void; title?: string;
  newDefaults?: Record<string, any>; extraActions?: ReactNode;
}) {
  const r = RES[res];
  const can = useCan();
  const [status, setStatus] = useState('');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<{ key: string; dir: 'asc' | 'desc' } | null>(null);
  const [archived, setArchived] = useState(false);
  const [edit, setEdit] = useState<{ id?: number } | null>(null);
  const limit = embedded ? 10 : 50;
  const list = useQuery({
    queryKey: ['list', res, { status, q, page, sort, archived, filter }],
    queryFn: () => api.get(`/api/r/${res}${qs({ status, q, page, limit, sort: sort?.key, dir: sort?.dir, archived: archived ? 1 : 0, ...(filter ?? {}) })}`),
    placeholderData: (p) => p,
  });
  const cols = useMemo(() => r.fields.filter((f) => f.list && !(filter && f.key in filter)), [r, filter]);
  const statusField = r.statusField ? r.fields.find((f) => f.key === r.statusField) : undefined;
  const canCreate = can(r.area, 'edit') || !!r.ownerScoped;
  const total = list.data?.total ?? 0;
  const counts: Record<string, number> = list.data?.counts ?? {};
  const allCount = Object.values(counts).reduce((a, b) => a + b, 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {!embedded ? (
        <div className="page-head">
          <div className="titles">
            <div className="eyebrow">{groupOf(r) ?? 'Weststar ONE'}</div>
            <h1>{title ?? r.label}</h1>
            <p className="desc">{r.description}</p>
          </div>
          {extraActions}
          {canCreate && <button className="btn primary" onClick={() => setEdit({})}><Icon name="plus" size={16} />{r.primaryAction ?? `New ${r.singular.toLowerCase()}`}</button>}
        </div>
      ) : (
        <div className="page-head" style={{ alignItems: 'center' }}>
          <h3 style={{ flex: 1 }}>{title ?? r.label} <span className="muted small">{total}</span></h3>
          {canCreate && <button className="btn small" onClick={() => setEdit({})}><Icon name="plus" size={14} />Add {r.singular.toLowerCase()}</button>}
        </div>
      )}
      {!embedded && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
          {statusField && (
            <div className="tabs scroll" role="tablist" aria-label="Filter by status">
              <button role="tab" aria-selected={!status && !archived} className={`tab ${!status && !archived ? 'on' : ''}`} onClick={() => { setStatus(''); setArchived(false); setPage(1); }}>All <span className="muted">{allCount}</span></button>
              {statusField.options!.map((o) => (
                <button key={o} role="tab" aria-selected={status === o} className={`tab ${status === o ? 'on' : ''}`} onClick={() => { setStatus(o); setArchived(false); setPage(1); }}>{o} <span className="muted">{counts[o] ?? 0}</span></button>
              ))}
            </div>
          )}
          <div className="search" style={{ maxWidth: 320 }}>
            <Icon name="search" size={16} />
            <label htmlFor={`q-${res}`} className="sr">Search {r.label}</label>
            <input id={`q-${res}`} placeholder={`Search ${r.label.toLowerCase()}…`} value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
          </div>
          {can(r.area, 'manage') && <button className={`chip ${archived ? 'on' : ''}`} aria-pressed={archived} onClick={() => { setArchived(!archived); setStatus(''); setPage(1); }}>Archived</button>}
        </div>
      )}
      {list.isError && <p className="banner">{errMsg(list.error)}</p>}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div className="table-wrap">
          <table className="grid">
            <thead><tr>{cols.map((f) => (
              <th key={f.key} aria-sort={sort?.key === f.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : undefined}>
                <button onClick={() => setSort((s) => (s?.key === f.key ? { key: f.key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key: f.key, dir: 'asc' }))}>{f.label}{sort?.key === f.key ? (sort.dir === 'asc' ? ' ↑' : ' ↓') : ''}</button>
              </th>
            ))}</tr></thead>
            <tbody>
              {(list.data?.rows ?? []).map((row: any) => (
                <tr key={row.id} tabIndex={0} onClick={() => (onOpen ? onOpen(row) : setEdit({ id: row.id }))} onKeyDown={(e) => { if (e.key === 'Enter') (onOpen ? onOpen(row) : setEdit({ id: row.id })); }}>
                  {cols.map((f, i) => <td key={f.key} className={i === 0 ? 'strong' : ''}>{cellValue(f, row, list.data.labels ?? {})}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {list.isLoading && <div className="empty">Loading…</div>}
        {list.data && list.data.rows.length === 0 && (
          <div className="empty">{q || status ? 'Nothing matches. Try another filter or clear the search.' : archived ? 'Nothing is archived.' : `No ${r.label.toLowerCase()} yet.`}{!q && !status && !archived && canCreate && <> <button className="link-btn" onClick={() => setEdit({})}>Add the first one</button></>}</div>
        )}
        {total > limit && (
          <div className="pager">
            <span className="muted small num">{(page - 1) * limit + 1}–{Math.min(page * limit, total)} of {total}</span>
            <div style={{ display: 'flex', gap: 6 }}>
              <button className="btn small" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button>
              <button className="btn small" disabled={page * limit >= total} onClick={() => setPage(page + 1)}>Next</button>
            </div>
          </div>
        )}
      </div>
      {edit && <ResourceForm res={res} id={edit.id} defaults={{ ...(filter ?? {}), ...(newDefaults ?? {}) }} onClose={() => setEdit(null)} />}
    </div>
  );
}
