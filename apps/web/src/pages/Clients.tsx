import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { RES } from '@ws/shared';
import { api, money, qs } from '../lib/api';
import { useCan } from '../lib/auth';
import { ResourceForm, ResourceList, cellValue } from '../components/Resource';
import { Later, Pill, errMsg, prioClass } from '../components/ui';
import { Icon } from '../components/Icon';
import { NewTicketDialog } from './Tickets';

export function ClientsPage() {
  const navigate = useNavigate();
  return <div className="page"><ResourceList res="clients" onOpen={(row) => navigate(`/clients/${row.id}`)} /></div>;
}

// Same tabs as the old client page; the ones backed by a module show live data.
const TABS: [string, string | null][] = [
  ['Overview', null], ['Contacts', 'contacts'], ['Tickets', null], ['Assets', 'assets'], ['Network', 'networks'],
  ['Contracts', 'contracts'], ['Invoices', 'invoices'], ['Quotes', 'quotes'], ['Projects', 'projects'], ['Notes', 'client_notes'],
  ['Domains', 'domains'], ['Policies', 'policies'], ['Training', 'training'], ['Files', null], ['Checklists', null], ['Portal', null],
];

export function ClientDetail() {
  const { id } = useParams();
  const cid = Number(id);
  const can = useCan();
  const [tab, setTab] = useState('Overview');
  const [editing, setEditing] = useState(false);
  const [newTicket, setNewTicket] = useState(false);
  const c = useQuery({ queryKey: ['r', 'clients', cid], queryFn: () => api.get(`/api/r/clients/${cid}`) });
  const tickets = useQuery({ queryKey: ['tickets', 'client', cid], queryFn: () => api.get(`/api/tickets${qs({ client_id: cid, filter: 'all', limit: 20 })}`), enabled: can('tickets') });
  if (c.isLoading) return <div className="page"><p className="muted">Loading…</p></div>;
  if (c.isError) return <div className="page"><p className="banner">{errMsg(c.error)}</p></div>;
  const row = c.data.row; const labels = c.data.labels ?? {};
  const r = RES.clients;
  const tabs = TABS.filter(([, res]) => !res || can(RES[res].area));
  const f = (k: string) => r.fields.find((x) => x.key === k)!;
  return (
    <div className="page">
      <div className="page-head">
        <div className="titles">
          <Link to="/clients" className="link-btn"><Icon name="back" size={16} />All clients</Link>
          <h1>{row.name}</h1>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
            <Pill v={row.status} />{row.plan && <Pill v={row.plan} cls="info" />}{row.archived_at && <Pill v="Archived" cls="bad" />}
          </div>
        </div>
        {can('clients', 'edit') && <button className="btn" onClick={() => setEditing(true)}>Edit client</button>}
        {can('tickets', 'edit') && <button className="btn primary" onClick={() => setNewTicket(true)}><Icon name="plus" size={16} />New ticket</button>}
      </div>
      {row.account_alert && <div className="alert-line">⚠ {row.account_alert}</div>}
      <div className="tabs scroll" role="tablist" aria-label="Client sections">
        {tabs.map(([t]) => <button key={t} role="tab" aria-selected={tab === t} className={`tab ${tab === t ? 'on' : ''}`} onClick={() => setTab(t)}>{t}</button>)}
      </div>

      {tab === 'Overview' && (
        <div className="split">
          <section className="card pad" style={{ flex: '1 1 320px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 14 }}>
            <h2>Account</h2>
            <div className="kv">
              {['phone', 'email', 'website', 'city', 'state', 'account_manager_id', 'hourly_rate', 'net_terms', 'sla_response_hours', 'sla_resolution_hours'].map((k) => (
                <div key={k}><div className="label">{f(k).label}</div><div>{cellValue(f(k), row, labels)}</div></div>
              ))}
            </div>
            {row.address && <div><div className="label">Address</div>{row.address}{row.city ? `, ${row.city}` : ''} {row.state ?? ''} {row.zip ?? ''}</div>}
            {row.notes && <div><div className="label">Internal notes</div><p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{row.notes}</p></div>}
          </section>
          <section className="card" style={{ flex: '1.4 1 380px', minWidth: 0, overflow: 'hidden' }}>
            <div style={{ padding: '16px 18px 8px', display: 'flex', justifyContent: 'space-between' }}><h2>Recent tickets</h2><span className="small muted">{tickets.data?.counts?.open ?? 0} open</span></div>
            <TicketRows rows={tickets.data?.rows ?? []} />
          </section>
        </div>
      )}
      {tab === 'Tickets' && <section className="card" style={{ overflow: 'hidden' }}><TicketRows rows={tickets.data?.rows ?? []} /></section>}
      {TABS.filter(([t, res]) => t === tab && res).map(([t, res]) => <ResourceList key={t} res={res!} embedded title={t} filter={{ client_id: cid }} />)}
      {tab === 'Invoices' && can('billing') && <BalanceNote clientId={cid} />}
      {['Files', 'Checklists', 'Portal'].includes(tab) && <Later what={`${row.name} · ${tab}`} />}

      {editing && <ResourceForm res="clients" id={cid} onClose={() => setEditing(false)} />}
      {newTicket && <NewTicketDialog clientId={cid} clientName={row.name} onClose={() => setNewTicket(false)} />}
    </div>
  );
}

function TicketRows({ rows }: { rows: any[] }) {
  if (!rows.length) return <div className="empty">No tickets for this client.</div>;
  return (
    <div className="table-wrap"><table className="grid"><tbody>
      {rows.map((t) => (
        <tr key={t.id}>
          <td className="small muted num" style={{ width: 90 }}><Link to={`/tickets/${t.id}`}>{t.number}</Link></td>
          <td className="strong"><Link to={`/tickets/${t.id}`} style={{ color: 'inherit', textDecoration: 'none' }}>{t.subject}</Link></td>
          <td><Pill v={t.priority} cls={prioClass(t.priority)} /></td>
          <td><Pill v={t.status} /></td>
        </tr>
      ))}
    </tbody></table></div>
  );
}

function BalanceNote({ clientId }: { clientId: number }) {
  const q = useQuery({ queryKey: ['list', 'invoices', 'bal', clientId], queryFn: () => api.get(`/api/r/invoices${qs({ client_id: clientId, limit: 200 })}`) });
  const open = (q.data?.rows ?? []).filter((x: any) => ['Sent', 'Viewed', 'Partial', 'Overdue'].includes(x.status));
  const owed = open.reduce((a: number, x: any) => a + Number(x.total ?? 0) - Number(x.amount_paid ?? 0), 0);
  return <p className="muted">Open balance: <b style={{ color: 'var(--text)' }}>{money(owed)}</b> across {open.length} invoice{open.length === 1 ? '' : 's'}.</p>;
}
