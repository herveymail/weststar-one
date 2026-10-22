import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api, ago, money } from '../lib/api';
import { useAuth } from '../lib/auth';
import { Pill, prioClass } from '../components/ui';

export function Dashboard() {
  const { me } = useAuth();
  const d = useQuery({ queryKey: ['dashboard'], queryFn: () => api.get('/api/dashboard'), refetchInterval: 60_000 });
  const t = d.data?.tickets, b = d.data?.billing, tl = d.data?.tools;
  const hour = new Date().getHours();
  return (
    <div className="page">
      <div className="page-head">
        <div className="titles">
          <div className="eyebrow">{new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</div>
          <h1>Good {hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening'}, {me.user?.name.split(' ')[0]}</h1>
          {d.data?.welcome && <p className="desc">{d.data.welcome}</p>}
        </div>
      </div>
      <div className="stats">
        {t && <>
          <Link to="/tickets" className="card stat"><span className="label">Open tickets</span><span className="v">{t.open}</span></Link>
          <Link to="/tickets" className={`card stat ${t.risk ? 'alert' : ''}`}><span className="label">SLA at risk</span><span className="v">{t.risk}</span></Link>
          <Link to="/tickets" className="card stat"><span className="label">Unassigned</span><span className="v">{t.unassigned}</span></Link>
          <Link to="/tickets" className="card stat"><span className="label">Assigned to me</span><span className="v">{t.mine}</span></Link>
        </>}
        {b && <>
          <Link to="/invoices" className="card stat"><span className="label">Unpaid invoices</span><span className="v">{money(b.unpaidAmount)}</span><span className="small muted">{b.unpaid} invoice{b.unpaid === 1 ? '' : 's'}</span></Link>
          <Link to="/invoices" className={`card stat ${b.overdue ? 'alert' : ''}`}><span className="label">Overdue</span><span className="v">{b.overdue}</span></Link>
        </>}
        {tl && <>
          <Link to="/backups" className={`card stat ${tl.backupFailures ? 'alert' : ''}`}><span className="label">Backup failures</span><span className="v">{tl.backupFailures}</span></Link>
          <Link to="/domains" className="card stat"><span className="label">Domains expiring in 30 days</span><span className="v">{tl.domainsExpiring}</span></Link>
        </>}
      </div>
      {d.data?.attention && (
        <section className="card" style={{ overflow: 'hidden' }}>
          <div style={{ padding: '16px 18px 8px' }}><h2>Needs attention</h2><p className="desc small">Critical tickets and anything close to missing its response time.</p></div>
          {d.data.attention.length === 0 && <div className="empty">Nothing urgent right now.</div>}
          <div className="table-wrap">
            <table className="grid"><tbody>
              {d.data.attention.map((x: any) => (
                <tr key={x.id}>
                  <td className="small muted num" style={{ width: 90 }}><Link to={`/tickets/${x.id}`}>{x.number}</Link></td>
                  <td className="strong"><Link to={`/tickets/${x.id}`} style={{ color: 'inherit', textDecoration: 'none' }}>{x.subject}</Link></td>
                  <td><Pill v={x.priority} cls={prioClass(x.priority)} /></td>
                  <td className="small muted">{x.response_due_at ? `due ${ago(x.response_due_at)}` : ''}</td>
                </tr>
              ))}
            </tbody></table>
          </div>
        </section>
      )}
    </div>
  );
}
