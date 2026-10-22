import { useEffect, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { TICKET_PRIORITIES, TICKET_STATUSES } from '@ws/shared';
import { api, ago, fmtDateTime, initials, qs } from '../lib/api';
import { useAuth, useCan } from '../lib/auth';
import { Dialog, Pill, errMsg, prioClass, statusClass, useToast } from '../components/ui';
import { RefPicker } from '../components/fields';
import { Icon } from '../components/Icon';

type View = 'inbox' | 'board' | 'queue';
type Filter = 'open' | 'unassigned' | 'risk' | 'all' | 'closed';

const slaText = (t: any) => {
  if (t.sla === 'done') return t.status;
  if (t.sla === 'paused') return 'Paused';
  if (t.first_response_at || !t.response_due_at) return ago(t.updated_at);
  const ms = new Date(t.response_due_at).getTime() - Date.now();
  if (ms < 0) return `Late ${fmtMins(-ms)}`;
  return fmtMins(ms);
};
const fmtMins = (ms: number) => { const m = Math.round(ms / 60000); return m < 60 ? `${m}m` : m < 1440 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${Math.floor(m / 1440)}d`; };

export function TicketsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [view, setView] = useState<View>(() => (localStorage.getItem('ws.tickets.view') as View) || 'inbox');
  const [filter, setFilter] = useState<Filter>('open');
  const [q, setQ] = useState('');
  useEffect(() => { try { localStorage.setItem('ws.tickets.view', view); } catch { /* ignore */ } }, [view]);
  const list = useQuery({
    queryKey: ['tickets', view, filter, q], enabled: view !== 'board',
    queryFn: () => api.get(`/api/tickets${qs({ view, filter, q })}`), refetchInterval: 30_000, placeholderData: (p) => p,
  });
  const board = useQuery({ queryKey: ['tickets-board', q], enabled: view === 'board', queryFn: () => api.get(`/api/tickets/board${qs({ q })}`), refetchInterval: 30_000 });
  const rows: any[] = list.data?.rows ?? [];
  const selected = id ? Number(id) : rows[0]?.id;
  const counts = list.data?.counts ?? {};

  return (
    <div className="page">
      <div className="page-head" style={{ alignItems: 'center' }}>
        <h1>Tickets</h1>
        <div className="tabs" role="tablist" aria-label="Ticket views">
          {(['inbox', 'board', 'queue'] as View[]).map((v) => <button key={v} role="tab" aria-selected={view === v} className={`tab ${view === v ? 'on' : ''}`} onClick={() => setView(v)}>{v === 'queue' ? 'My queue' : v[0].toUpperCase() + v.slice(1)}</button>)}
        </div>
        {view !== 'board' && (
          <div className="chips">
            {([['open', 'Open'], ['unassigned', 'Unassigned'], ['risk', 'SLA at risk'], ['closed', 'Closed'], ['all', 'All']] as [Filter, string][]).map(([k, l]) => (
              <button key={k} className={`chip ${filter === k ? 'on' : ''}`} aria-pressed={filter === k} onClick={() => setFilter(k)}>{l} · {counts[k] ?? 0}</button>
            ))}
          </div>
        )}
        <div className="search" style={{ maxWidth: 280 }}>
          <Icon name="search" size={16} /><label htmlFor="tq" className="sr">Filter tickets</label>
          <input id="tq" placeholder="Filter tickets…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>

      {view === 'board' ? (
        <div className="table-wrap">
          <div className="board">
            {[['New', ['New']], ['Open', ['Open', 'Scheduled']], ['Waiting', ['Waiting on client', 'Waiting on vendor']], ['Done', ['Resolved', 'Closed']]].map(([name, sts]) => {
              const cards = (board.data?.rows ?? []).filter((t: any) => (sts as string[]).includes(t.status));
              return (
                <section key={name as string} className="col" aria-label={name as string}>
                  <div className="col-head"><span>{name as string}</span><span className="muted">{cards.length}</span></div>
                  {cards.map((t: any) => (
                    <button key={t.id} className="b-card" onClick={() => { setView('inbox'); setFilter('all'); navigate(`/tickets/${t.id}`); }}>
                      <span className="small muted num">{t.number}</span>
                      <span className="strong" style={{ lineHeight: 1.35 }}>{t.subject}</span>
                      <span className="small muted">{t.client_name ?? 'No client'}</span>
                      <span style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}><Pill v={t.priority} cls={prioClass(t.priority)} /><span className="small muted">{t.assignee_name ?? 'Unassigned'}</span></span>
                    </button>
                  ))}
                </section>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="split">
          <section className="card t-list" aria-label="Ticket list">
            {rows.map((t) => {
              const closed = t.status === 'Resolved' || t.status === 'Closed';
              return (
                <button key={t.id} className={`t-row ${t.id === selected ? 'on' : ''}`} aria-pressed={t.id === selected} onClick={() => navigate(`/tickets/${t.id}`)}>
                  <span className="small muted num">{t.number}</span>
                  <span className={`subj ${closed ? 'closed' : ''}`}>{t.subject}</span>
                  <span className={`small strong num ${(t.sla === 'risk' || t.sla === 'breached') ? 'risk' : 'muted'}`} style={{ textAlign: 'right' }}>{slaText(t)}</span>
                  <span className="small muted">{t.assignee_name ?? 'Unassigned'}</span>
                  <span className="client">{t.client_name ?? t.contact_name ?? 'No client'}</span>
                  <span style={{ justifySelf: 'end' }}><Pill v={t.priority} cls={prioClass(t.priority)} /></span>
                </button>
              );
            })}
            {list.isLoading && <div className="empty">Loading…</div>}
            {list.data && rows.length === 0 && <div className="empty">No tickets here. {filter !== 'all' && <button className="link-btn" onClick={() => setFilter('all')}>Show all</button>}</div>}
          </section>
          {selected ? <TicketPane id={selected} /> : <section className="card t-pane"><div className="empty">Pick a ticket to see it here.</div></section>}
        </div>
      )}
    </div>
  );
}

function TicketPane({ id }: { id: number }) {
  const { me } = useAuth();
  const can = useCan();
  const toast = useToast();
  const qc = useQueryClient();
  const d = useQuery({ queryKey: ['ticket', id], queryFn: () => api.get(`/api/tickets/${id}`), refetchInterval: 20_000 });
  const [mode, setMode] = useState<'reply' | 'note'>('reply');
  const [draft, setDraft] = useState('');
  const [minutes, setMinutes] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { setDraft(''); setMinutes(''); }, [id]);
  const refresh = () => { qc.invalidateQueries({ queryKey: ['ticket', id] }); qc.invalidateQueries({ queryKey: ['tickets'] }); qc.invalidateQueries({ queryKey: ['ticket-counts'] }); };
  const patch = async (body: Record<string, unknown>, msg: string) => {
    try { await api.patch(`/api/tickets/${id}`, body); toast(msg); refresh(); } catch (e) { toast(errMsg(e), 'err'); }
  };
  const send = async () => {
    if (!draft.trim()) return;
    setBusy(true);
    try { await api.post(`/api/tickets/${id}/messages`, { kind: mode, body: draft, minutes: Number(minutes || 0) }); setDraft(''); setMinutes(''); toast(mode === 'note' ? 'Note added.' : 'Reply saved.'); refresh(); }
    catch (e) { toast(errMsg(e), 'err'); } finally { setBusy(false); }
  };
  const logTime = async () => {
    const m = Number(minutes || 15);
    try { await api.post(`/api/tickets/${id}/time`, { minutes: m }); setMinutes(''); toast(`Logged ${m} min.`); refresh(); } catch (e) { toast(errMsg(e), 'err'); }
  };
  if (d.isLoading) return <section className="card t-pane"><div className="empty">Loading…</div></section>;
  if (d.isError) return <section className="card t-pane"><div className="empty">{errMsg(d.error)}</div></section>;
  const t = d.data.ticket; const client = d.data.client;
  const edit = can('tickets', 'edit');
  const closed = t.status === 'Closed' || t.status === 'Resolved';
  const late = t.sla === 'risk' || t.sla === 'breached';
  const mins = d.data.minutes as number;
  return (
    <section className="card t-pane" aria-label="Selected ticket">
      <div className="t-head">
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
          <span className="small muted num">{t.number}</span>
          <Pill v={t.priority} cls={prioClass(t.priority)} />
          <Pill v={t.status} cls={statusClass(t.status)} />
          <span className={`small strong ${late ? 'risk' : 'muted'}`} style={late ? { color: 'var(--crit)' } : undefined}>
            {closed ? `${t.status} ${ago(t.closed_at ?? t.resolved_at)}` : t.sla === 'paused' ? 'SLA paused while waiting' : t.first_response_at ? `Answered ${ago(t.first_response_at)}` : t.response_due_at ? (late ? `Response due ${new Date(t.response_due_at) < new Date() ? 'overdue' : 'in ' + slaText(t)}` : `Response due in ${slaText(t)}`) : ''}
          </span>
          <span className="spacer" />
          <Link className="link-btn small" to={`/tickets/${t.id}`}>Link</Link>
        </div>
        <h2>{t.subject}</h2>
        {client?.account_alert && <div className="alert-line">⚠ {client.account_alert}</div>}
        <div className="t-meta">
          <div><div className="label">Client</div>{client ? <Link className="link-btn" to={`/clients/${client.id}`}>{client.name}</Link> : <span className="muted">None</span>}</div>
          <div><div className="label">Contact</div>{t.contact_name ?? <span className="muted">—</span>}{t.contact_email && <div className="small muted">{t.contact_email}</div>}</div>
          {client?.plan && <div><div className="label">Plan</div>{client.plan}</div>}
          <div><div className="label">Assigned</div>
            {edit ? (
              <div style={{ minWidth: 180 }}><RefPicker id="assign" refRes="users" value={t.assigned_to} label={t.assignee_name ?? ''} onChange={(v) => patch({ assigned_to: v }, v ? 'Assigned.' : 'Unassigned.')} /></div>
            ) : t.assignee_name ?? 'Unassigned'}
            {edit && t.assigned_to !== me.user?.id && <button className="link-btn small" onClick={() => patch({ assigned_to: me.user!.id }, 'Assigned to you.')}>Assign to me</button>}
          </div>
          <div><div className="label">Time logged</div><span className="num">{mins ? `${Math.floor(mins / 60) ? Math.floor(mins / 60) + 'h ' : ''}${mins % 60 ? (mins % 60) + 'm' : ''}` : 'None yet'}</span></div>
        </div>
        {edit && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            <label className="sr" htmlFor="t-status">Status</label>
            <select id="t-status" className="select" style={{ width: 'auto' }} value={t.status} onChange={(e) => patch({ status: e.target.value }, `Status: ${e.target.value}`)}>
              {TICKET_STATUSES.map((s) => <option key={s}>{s}</option>)}
            </select>
            <label className="sr" htmlFor="t-prio">Priority</label>
            <select id="t-prio" className="select" style={{ width: 'auto' }} value={t.priority} onChange={(e) => patch({ priority: e.target.value }, `Priority: ${e.target.value}`)}>
              {TICKET_PRIORITIES.map((p) => <option key={p}>{p}</option>)}
            </select>
          </div>
        )}
      </div>
      <div className="t-conv">
        {d.data.messages.map((m: any) => m.kind === 'event' ? (
          <div key={m.id} className="event">{m.body} · {ago(m.created_at)}</div>
        ) : (
          <div key={m.id} className="msg">
            <div className={`av ${m.author_user_id === me.user?.id ? 'me' : ''}`}>{initials(m.author_name)}</div>
            <div className={`bubble ${m.kind === 'note' ? 'note' : ''}`}>
              <div className="meta"><b style={{ color: 'var(--text)' }}>{m.author_name ?? 'Unknown'}</b> · {fmtDateTime(m.created_at)} · {m.kind === 'note' ? 'internal note' : m.via}</div>
              <p className="body">{m.body}</p>
            </div>
          </div>
        ))}
      </div>
      {edit && (
        <div className="reply">
          <div className="tabs" role="tablist" aria-label="Reply type" style={{ alignSelf: 'flex-start' }}>
            <button role="tab" aria-selected={mode === 'reply'} className={`tab ${mode === 'reply' ? 'on' : ''}`} onClick={() => setMode('reply')}>Reply to client</button>
            <button role="tab" aria-selected={mode === 'note'} className={`tab ${mode === 'note' ? 'on' : ''}`} onClick={() => setMode('note')}>Internal note</button>
          </div>
          <label htmlFor="reply" className="sr">Message</label>
          <textarea id="reply" className={`textarea ${mode === 'note' ? 'note' : ''}`} rows={3} placeholder={mode === 'note' ? 'Only your team sees internal notes…' : `Write a reply${t.contact_name ? ' to ' + t.contact_name : ''}…`}
            value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) send(); }} />
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
            <button className="btn primary" disabled={!draft.trim() || busy} onClick={send}>{mode === 'note' ? 'Add note' : 'Save reply'}</button>
            <label className="sr" htmlFor="mins">Minutes</label>
            <input id="mins" className="input num" style={{ width: 90 }} type="number" min={0} max={1440} placeholder="Min" value={minutes} onChange={(e) => setMinutes(e.target.value)} />
            <button className="btn" onClick={logTime}>Log {minutes || 15} min</button>
            <span className="spacer" />
            <button className="btn" onClick={() => patch({ status: closed ? 'Open' : 'Closed' }, closed ? 'Reopened.' : 'Closed.')}>{closed ? 'Reopen ticket' : 'Close ticket'}</button>
          </div>
          <span className="small muted">Replies are saved to the ticket. Emailing them to the client arrives with the Microsoft 365 connection in the next round.</span>
        </div>
      )}
    </section>
  );
}

export function NewTicketDialog({ onClose, clientId, clientName }: { onClose: () => void; clientId?: number; clientName?: string }) {
  const toast = useToast();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [f, setF] = useState<{ subject: string; details: string; client_id: number | null; client_label: string; contact_id: number | null; priority: string }>({ subject: '', details: '', client_id: clientId ?? null, client_label: clientName ?? '', contact_id: null, priority: 'Medium' });
  const [busy, setBusy] = useState(false);
  const create = async () => {
    setBusy(true);
    try {
      const r = await api.post('/api/tickets', { subject: f.subject, details: f.details, client_id: f.client_id, contact_id: f.contact_id, priority: f.priority });
      toast(`Created ${r.ticket.number}.`); qc.invalidateQueries({ queryKey: ['tickets'] }); qc.invalidateQueries({ queryKey: ['ticket-counts'] });
      onClose(); navigate(`/tickets/${r.ticket.id}`);
    } catch (e) { toast(errMsg(e), 'err'); } finally { setBusy(false); }
  };
  return (
    <Dialog title="New ticket" onClose={onClose}>
      <form style={{ display: 'flex', flexDirection: 'column', gap: 14 }} onSubmit={(e) => { e.preventDefault(); create(); }}>
        <div className="field"><label htmlFor="nt-s">Subject *</label><input id="nt-s" className="input" autoFocus required maxLength={255} value={f.subject} onChange={(e) => setF({ ...f, subject: e.target.value })} placeholder="What's going on?" /></div>
        <div className="form-grid">
          <div className="field"><label htmlFor="nt-c">Client</label><RefPicker id="nt-c" refRes="clients" value={f.client_id} label={f.client_label} onChange={(v, l) => setF({ ...f, client_id: v, client_label: l ?? '', contact_id: null })} /></div>
          <div className="field"><label htmlFor="nt-k">Contact</label><RefPicker id="nt-k" refRes="contacts" value={f.contact_id} filter={f.client_id ? { client_id: f.client_id } : undefined} onChange={(v) => setF({ ...f, contact_id: v })} /></div>
          <div className="field"><label htmlFor="nt-p">Priority</label><select id="nt-p" className="select" value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}>{TICKET_PRIORITIES.map((p) => <option key={p}>{p}</option>)}</select></div>
        </div>
        <div className="field"><label htmlFor="nt-d">Details</label><textarea id="nt-d" className="textarea" value={f.details} onChange={(e) => setF({ ...f, details: e.target.value })} /></div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn primary" disabled={!f.subject.trim() || busy}>{busy ? 'Creating…' : 'Create ticket'}</button>
        </div>
      </form>
    </Dialog>
  );
}
