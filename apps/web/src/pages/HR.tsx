import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, qs } from '../lib/api';
import { useAuth, useCan } from '../lib/auth';
import { ResourceList } from '../components/Resource';

/** My HR: your own time off and timeclock (the API only ever returns your own rows here). */
export function MyHR() {
  const { me } = useAuth();
  const [tab, setTab] = useState<'pto' | 'timeclock' | 'mileage'>('pto');
  const emp = useQuery({ queryKey: ['my-emp'], queryFn: () => api.get(`/api/r/employees${qs({ user_id: me.user?.id, limit: 1 })}`).catch(() => null) });
  const e = emp.data?.rows?.[0];
  return (
    <div className="page">
      <div className="page-head"><div className="titles"><div className="eyebrow">H/R</div><h1>My HR</h1><p className="desc">Your time off, timeclock and mileage. Only you and H/R can see these.</p></div></div>
      <div className="stats">
        <div className="card stat"><span className="label">Signed in as</span><span className="v" style={{ fontSize: 18 }}>{me.user?.name}</span><span className="small muted">{me.user?.title ?? me.user?.role}</span></div>
        {e && <div className="card stat"><span className="label">PTO balance</span><span className="v">{e.pto_balance_hours ?? '—'} h</span></div>}
      </div>
      <div className="tabs" role="tablist" aria-label="My HR sections">
        {([['pto', 'Time off'], ['timeclock', 'Timeclock'], ['mileage', 'Mileage']] as const).map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? 'on' : ''}`} onClick={() => setTab(k)}>{l}</button>)}
      </div>
      <ResourceList key={tab} res={tab} embedded title={tab === 'pto' ? 'My time off' : tab === 'timeclock' ? 'My time entries' : 'My trips'} />
    </div>
  );
}

/** H/R Admin: same sections as the old H/R hub — employees, timeclock approvals, time-off requests. */
export function HRAdmin() {
  const can = useCan();
  const [tab, setTab] = useState<'employees' | 'pto' | 'timeclock'>('employees');
  if (!can('hr')) return <div className="page"><p className="banner">You need H/R access for this page. An admin can turn it on in Settings › Staff users.</p></div>;
  return (
    <div className="page">
      <div className="tabs" role="tablist" aria-label="H/R sections">
        {([['employees', 'Employees'], ['timeclock', 'Timeclock'], ['pto', 'Time off requests']] as const).map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? 'on' : ''}`} onClick={() => setTab(k)}>{l}</button>)}
      </div>
      <ResourceList key={tab} res={tab} title={tab === 'employees' ? 'H/R Admin' : tab === 'pto' ? 'Time off requests' : 'Timeclock'} />
    </div>
  );
}
