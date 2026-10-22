/** Small fetch wrapper: same-origin cookies, CSRF header on writes, friendly errors. */
let csrf = '';
export const setCsrf = (t: string) => { csrf = t; };

export class ApiError extends Error {
  constructor(public status: number, message: string, public details?: { field: string; message: string }[]) { super(message); }
}

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers['content-type'] = 'application/json';
  if (method !== 'GET') headers['x-csrf-token'] = csrf;
  const res = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), credentials: 'same-origin' });
  const text = await res.text();
  let data: any = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { error: text }; }
  if (!res.ok) {
    if (res.status === 401 && !url.startsWith('/api/auth/')) window.dispatchEvent(new Event('ws:signed-out'));
    throw new ApiError(res.status, data?.error ?? `Request failed (${res.status})`, data?.details);
  }
  return data as T;
}

export const api = {
  get: <T = any>(url: string) => request<T>('GET', url),
  post: <T = any>(url: string, body?: unknown) => request<T>('POST', url, body ?? {}),
  patch: <T = any>(url: string, body?: unknown) => request<T>('PATCH', url, body ?? {}),
  put: <T = any>(url: string, body?: unknown) => request<T>('PUT', url, body ?? {}),
  del: <T = any>(url: string) => request<T>('DELETE', url),
};

export const qs = (o: Record<string, unknown>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(o)) if (v !== undefined && v !== null && v !== '') p.set(k, String(v));
  const s = p.toString();
  return s ? '?' + s : '';
};

export const money = (v: unknown) => {
  if (v === null || v === undefined || v === '') return '—';
  const n = Number(v);
  return Number.isFinite(n) ? n.toLocaleString('en-US', { style: 'currency', currency: 'USD' }) : String(v);
};
export const fmtDate = (v: unknown) => {
  if (!v) return '—';
  const s = String(v);
  const d = /^\d{4}-\d{2}-\d{2}$/.test(s) ? new Date(s + 'T12:00:00') : new Date(s);
  return Number.isNaN(d.getTime()) ? s : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};
export const fmtDateTime = (v: unknown) => {
  if (!v) return '—';
  const d = new Date(String(v));
  return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
};
export const ago = (v: unknown) => {
  if (!v) return '';
  const ms = Date.now() - new Date(String(v)).getTime();
  const m = Math.round(ms / 60000);
  if (Math.abs(m) < 1) return 'just now';
  if (m < 0) { const f = -m; return f < 60 ? `in ${f}m` : f < 1440 ? `in ${Math.round(f / 60)}h` : `in ${Math.round(f / 1440)}d`; }
  return m < 60 ? `${m}m ago` : m < 1440 ? `${Math.round(m / 60)}h ago` : `${Math.round(m / 1440)}d ago`;
};
export const initials = (name?: string | null) => (name ?? '?').split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join('') || '?';
