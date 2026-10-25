"""MSP360 Managed Backup — same behaviour as the old app's integration.

Pulls companies, computers and the latest run of every backup plan from the MSP360 API (api.mspbackups.com),
matches MSP360 companies to clients, and opens a ticket when a plan fails (a note on each later failed run,
resolved automatically when it succeeds again).

API: POST /api/Provider/Login {UserName, Password} → access_token (Bearer)
     GET /api/Companies · GET /api/Users · GET /api/Users/{id}/Computers · GET /api/Monitoring
Settings › MSP360 backups: msp360.* (login / password are the API credentials from MSP360 › Settings › General).
"""
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone as dt_tz

from django.db import transaction
from django.utils import timezone

from apps.core.models import Setting

from .models import FAILED, Msp360Company, Msp360Computer, Msp360Plan

DEFAULT_BASE = "https://api.mspbackups.com"
PLAN_TYPES = {0: "NA", 1: "Files", 2: "Image", 3: "SQL", 4: "Exchange", 5: "VMware", 6: "Hyper-V", 7: "Cloud", 8: "Consistency"}


class Msp360Error(Exception):
    pass


def cfg() -> dict:
    def b(k, d="true"):
        return Setting.get(k, d) != "false"
    try:
        hours = max(1, int(Setting.get("msp360.overdue_hours", "36") or 36))
    except ValueError:
        hours = 36
    return {
        "enabled": Setting.get("msp360.enabled", "false") == "true",
        "login": Setting.get("msp360.login", "").strip(),
        "password": Setting.get("msp360.password", ""),
        "base": (Setting.get("msp360.base_url", "") or DEFAULT_BASE).rstrip("/"),
        "tickets": b("msp360.ticket_on_failure"),
        "overdue_hours": hours,
        "priority": Setting.get("msp360.ticket_priority", "High") or "High",
        "auto_resolve": b("msp360.auto_resolve"),
        "queue": Setting.get("msp360.queue", ""),
    }


def configured(c: dict | None = None) -> bool:
    c = c or cfg()
    return bool(c["login"] and c["password"])


# ── HTTP ──
def _http(method: str, url: str, body=None, token: str = "") -> tuple[int, object]:
    """Returns (status, parsed JSON or text). Tests replace this function."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Accept": "application/json", "Content-Type": "application/json",
                                                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 — fixed https base from settings
            raw, code = r.read().decode("utf-8", "replace"), r.status
    except urllib.error.HTTPError as e:
        raw, code = e.read().decode("utf-8", "replace"), e.code
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise Msp360Error(f"Couldn't reach MSP360: {getattr(e, 'reason', e)}") from e
    try:
        return code, json.loads(raw) if raw else None
    except ValueError:
        return code, raw


def _message(payload) -> str:
    if isinstance(payload, dict):
        return str(payload.get("Message") or payload.get("error_description") or payload.get("error") or "")
    return str(payload or "")[:200]


def token(c: dict, fresh=False) -> str:
    if not configured(c):
        raise Msp360Error("Add the MSP360 API login and password first.")
    cached, at = Setting.get("msp360.token", ""), Setting.get("msp360.token_at", "0")
    if not fresh and cached and time.time() - float(at or 0) < 3000:
        return cached
    code, j = _http("POST", c["base"] + "/api/Provider/Login", {"UserName": c["login"], "Password": c["password"]})
    if code == 200 and isinstance(j, dict) and j.get("access_token"):
        Setting.put("msp360.token", j["access_token"], secret=True)
        Setting.put("msp360.token_at", str(time.time()))
        return j["access_token"]
    msg = _message(j) or f"HTTP {code}"
    if code in (400, 401, 403):
        msg += " — use the API login and password from MSP360 › Settings › General › API (not your portal sign-in)."
    raise Msp360Error(f"Sign-in failed: {msg}")


def get(path: str, c: dict):
    t = token(c)
    code, j = _http("GET", c["base"] + path, token=t)
    if code == 401:
        code, j = _http("GET", c["base"] + path, token=token(c, fresh=True))
    if 200 <= code < 300:
        return j
    raise Msp360Error(f"{_message(j) or 'HTTP ' + str(code)} ({path})")


def test() -> dict:
    c = cfg()
    try:
        token(c, fresh=True)
        companies = get("/api/Companies", c)
        plans = get("/api/Monitoring", c)
    except Msp360Error as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "companies": len(companies or []), "plans": len(plans or [])}


# ── matching companies to clients ──
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def match_client(name: str, clients: list | None = None):
    """Exact name, then a loose match (ignoring punctuation, LLC, etc.)."""
    from apps.crm.models import Client
    clients = clients if clients is not None else list(Client.objects.exclude(status="Former").filter(archived_at__isnull=True).only("id", "name"))
    k = (name or "").strip().lower()
    if not k:
        return None
    for c in clients:
        if c.name.strip().lower() == k:
            return c
    nk = re.sub(r"(llc|inc|pllc|ltd|co|corp)$", "", _norm(name))
    if len(nk) >= 4:
        for c in clients:
            nn = re.sub(r"(llc|inc|pllc|ltd|co|corp)$", "", _norm(c.name))
            if nn == nk or (nn and min(len(nn), len(nk)) >= 6 and (nk.startswith(nn) or nn.startswith(nk))):
                return c
    return None


def client_for(company: str):
    row = Msp360Company.objects.filter(name__iexact=(company or "").strip()).select_related("client").first()
    if row and row.client:
        return row.client
    return match_client(company)


# ── sync ──
def _dt(v):
    if not v or str(v).startswith("0001-01-01"):
        return None
    s = str(v).strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt_tz.utc)


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _computers(c: dict) -> list[dict]:
    """Every backup computer, via the users list (GET /api/Users/{id}/Computers)."""
    out = []
    users = get("/api/Users", c) or []
    for u in users if isinstance(users, list) else []:
        uid = u.get("ID") if isinstance(u, dict) else None
        if not uid:
            continue
        try:
            rows = get(f"/api/Users/{uid}/Computers", c) or []
        except Msp360Error:
            continue
        if isinstance(rows, dict):
            rows = rows.get("Computers") or rows.get("computers") or []
        for k in rows if isinstance(rows, list) else []:
            if isinstance(k, dict):
                k.setdefault("_company", u.get("Company") or "")
                k.setdefault("_email", u.get("Email") or "")
                out.append(k)
    return out


def sync(tickets: bool = True) -> dict:
    c = cfg()
    out = {"ok": False, "companies": 0, "computers": 0, "plans": 0, "failed": 0, "overdue": 0, "warning": 0, "success": 0,
           "tickets_opened": 0, "tickets_noted": 0, "tickets_resolved": 0, "unmatched": 0, "error": ""}
    started = time.time()
    now = timezone.now()
    try:
        companies = get("/api/Companies", c) or []
        clients = None
        from apps.crm.models import Client
        clients = list(Client.objects.exclude(status="Former").filter(archived_at__isnull=True).only("id", "name"))
        for co in companies:
            if not isinstance(co, dict) or not co.get("Id"):
                continue
            row = Msp360Company.objects.filter(pk=str(co["Id"])).first() or Msp360Company(mc_id=str(co["Id"]))
            row.name = str(co.get("Name") or "")[:190]
            if not row.client_id and not row.client_set_by_hand:
                m = match_client(row.name, clients)
                row.client = m
            row.storage_limit = _int(co.get("StorageLimit"))
            row.updated_at = now
            row.save()
            out["companies"] += 1

        try:
            computers = _computers(c)
        except Msp360Error:
            computers = []
        seen = []
        for k in computers:
            name = str(k.get("ComputerName") or k.get("Name") or k.get("DisplayName") or "").strip()
            if not name:
                continue
            company = str(k.get("CompanyName") or k.get("_company") or "")
            key = str(k.get("ComputerHID") or k.get("HID") or k.get("Id") or f"{company}/{name}")[:190]
            online = bool(k.get("Online") or k.get("IsOnline") or any(a.get("Online") for a in (k.get("Apps") or []) if isinstance(a, dict)))
            Msp360Computer.objects.update_or_create(key=key, defaults={
                "name": name[:190], "company": company[:190], "user_email": str(k.get("UserEmail") or k.get("_email") or "")[:190],
                "os": str(k.get("OSTypeString") or k.get("OperatingSystem") or k.get("OS") or "")[:60], "online": online,
                "last_activity": _dt(k.get("LastActivity") or k.get("LastOnline")), "updated_at": now})
            seen.append(key)
            out["computers"] += 1

        plans = get("/api/Monitoring", c) or []
        seen_plans = []
        for p in plans:
            if not isinstance(p, dict) or not p.get("PlanId"):
                continue
            status = _int(p.get("Status"))
            status = 4 if status is None else status
            pt = p.get("PlanType", 0)
            ptype = PLAN_TYPES.get(_int(pt), f"Type {pt}") if _int(pt) is not None else str(pt)
            pid = str(p["PlanId"])[:64]
            prev = Msp360Plan.objects.filter(pk=pid).first()
            failed_since = (prev.failed_since if prev and prev.failed_since else now) if status in FAILED else None
            Msp360Plan.objects.update_or_create(plan_id=pid, defaults={
                "name": str(p.get("PlanName") or "")[:255], "plan_type": ptype[:40], "computer": str(p.get("ComputerName") or "")[:190],
                "company": str(p.get("CompanyName") or "")[:190], "user_email": str(p.get("UserName") or "")[:190],
                "storage": str(p.get("StorageType") or "")[:80], "status": status,
                "last_start": _dt(p.get("LastStart")), "next_start": _dt(p.get("NextStart")), "error": str(p.get("ErrorMessage") or ""),
                "files_copied": _int(p.get("FilesCopied")), "files_failed": _int(p.get("FilesFailed")),
                "data_copied": _int(p.get("DataCopied")), "total_data": _int(p.get("TotalData")), "duration": str(p.get("Duration") or "")[:40],
                "report_link": str(p.get("DetailedReportLink") or "")[:500], "failed_since": failed_since,
                "first_seen": prev.first_seen if prev and prev.first_seen else now, "updated_at": now})
            seen_plans.append(pid)
            out["plans"] += 1
            if status in FAILED:
                out["failed"] += 1
            elif status == 1:
                out["overdue"] += 1
            elif status == 7:
                out["warning"] += 1
            elif status == 0:
                out["success"] += 1
            # computers MSP360 didn't list on their own still show up, from their plans
            ckey = f"{p.get('CompanyName') or ''}/{p.get('ComputerName') or ''}"[:190]
            if p.get("ComputerName") and not Msp360Computer.objects.filter(name=p.get("ComputerName"), company=p.get("CompanyName") or "").exists():
                Msp360Computer.objects.update_or_create(key=ckey, defaults={"name": str(p["ComputerName"])[:190], "company": str(p.get("CompanyName") or "")[:190],
                                                                           "user_email": str(p.get("UserName") or "")[:190], "online": True, "updated_at": now})
                seen.append(ckey)
                out["computers"] += 1
        Msp360Plan.objects.exclude(pk__in=seen_plans).delete()
        Msp360Computer.objects.exclude(pk__in=seen).delete()
        for co in Msp360Company.objects.all():
            n = Msp360Computer.objects.filter(company__iexact=co.name).count()
            if n != co.computers:
                Msp360Company.objects.filter(pk=co.pk).update(computers=n)
        for comp in Msp360Computer.objects.all():
            ps = Msp360Plan.objects.filter(computer=comp.name, company=comp.company)
            Msp360Computer.objects.filter(pk=comp.pk).update(plans=ps.count(), failed=ps.filter(status__in=FAILED).count())
        out["unmatched"] = Msp360Company.objects.filter(client__isnull=True).count()
        if tickets and c["tickets"]:
            out.update(ticket_pass(c))
    except Msp360Error as e:
        out["error"] = str(e)
        Setting.put("msp360.last_error", out["error"])
        Setting.put("msp360.last_attempt", now.isoformat())
        return out
    out["ok"] = True
    out["seconds"] = round(time.time() - started, 1)
    Setting.put("msp360.last_sync", now.isoformat())
    Setting.put("msp360.last_attempt", now.isoformat())
    Setting.put("msp360.last_error", "")
    Setting.put("msp360.last_summary", json.dumps(out))
    return out


# ── tickets ──
def _queue(c):
    from apps.helpdesk.models import Queue
    q = c.get("queue") or ""
    return Queue.objects.filter(pk=int(q)).first() if q.isdigit() else None


def _note(ticket, body):
    from apps.helpdesk.models import TicketMessage
    TicketMessage.objects.create(ticket=ticket, kind="note", body=body, author_name="MSP360", via="system")


def _when(d):
    return timezone.localtime(d).strftime("%b %-d, %Y %-I:%M %p") if d else ""


def ticket_pass(c: dict | None = None) -> dict:
    from apps.helpdesk import services
    from apps.helpdesk.models import DONE_STATUSES
    c = c or cfg()
    res = {"tickets_opened": 0, "tickets_noted": 0, "tickets_resolved": 0}
    overdue_cut = timezone.now() - timedelta(hours=c["overdue_hours"])
    for p in Msp360Plan.objects.select_related("ticket"):
        bad = p.status in FAILED or (p.status == 1 and p.next_start and p.next_start < overdue_cut)
        t = p.ticket
        is_open = t is not None and t.status not in DONE_STATUSES and t.merged_into_id is None
        if bad:
            if is_open:
                if p.last_start and p.last_start != p.ticket_last_start:
                    _note(t, f"MSP360: still {p.status_label} after the run at {_when(p.last_start)}." + (f"\nError: {p.error}" if p.error else ""))
                    Msp360Plan.objects.filter(pk=p.pk).update(ticket_last_start=p.last_start)
                    res["tickets_noted"] += 1
                continue
            lines = [f"MSP360 reports backup plan \"{p.name}\" on {p.computer or 'an unknown computer'}" + (f" ({p.company})" if p.company else "") + f" is {p.status_label}."]
            if p.error:
                lines.append(f"\nError: {p.error}")
            if p.last_start:
                lines.append(f"Last run: {_when(p.last_start)}" + (f" ({p.duration})" if p.duration else ""))
            if p.next_start:
                lines.append(f"Next run: {_when(p.next_start)}")
            if p.files_failed:
                lines.append(f"Files failed: {p.files_failed}")
            if p.report_link:
                lines.append(f"\nDetailed report: {p.report_link}")
            lines.append(f"\nAgent: {p.user_email or '—'} · Plan type: {p.plan_type or '—'} · Storage: {p.storage or '—'}")
            with transaction.atomic():
                new = services.create_ticket(subject=f"Backup {p.status_label.lower()}: {p.computer or 'Unknown computer'} — {p.name}"[:255],
                                             details="\n".join(lines), client=client_for(p.company), priority=c["priority"],
                                             source="MSP360", queue=_queue(c), category="Backup")
                Msp360Plan.objects.filter(pk=p.pk).update(ticket=new, ticket_last_start=p.last_start)
            res["tickets_opened"] += 1
        elif is_open and p.status == 0:
            _note(t, f"MSP360: plan \"{p.name}\" on {p.computer} completed successfully at {_when(p.last_start) or 'the last run'}."
                     + (" Ticket resolved automatically." if c["auto_resolve"] else ""))
            if c["auto_resolve"]:
                type(t).objects.filter(pk=t.pk).update(status="Resolved", resolved_at=timezone.now(),
                                                       resolution=t.resolution or "Backup completed successfully (MSP360)")
                services.event(t, "Resolved automatically: the backup succeeded (MSP360)")
                res["tickets_resolved"] += 1
            else:
                res["tickets_noted"] += 1
            Msp360Plan.objects.filter(pk=p.pk).update(ticket=None, ticket_last_start=None)
    return res


# ── for pages ──
def summary() -> dict:
    from django.db.models import Count
    s = {"computers": Msp360Computer.objects.count(), "online": Msp360Computer.objects.filter(online=True).count(),
         "plans": 0, "success": 0, "warning": 0, "failed": 0, "overdue": 0, "running": 0, "unknown": 0,
         "unmatched": Msp360Company.objects.filter(client__isnull=True).count(),
         "open_tickets": Msp360Plan.objects.filter(ticket__isnull=False).exclude(ticket__status__in=["Resolved", "Closed"]).count(),
         "last_sync": Setting.get("msp360.last_sync", ""), "last_error": Setting.get("msp360.last_error", "")}
    for r in Msp360Plan.objects.values("status").annotate(n=Count("pk")):
        st, n = r["status"], r["n"]
        s["plans"] += n
        key = "success" if st == 0 else "warning" if st == 7 else "overdue" if st == 1 else "running" if st == 3 else "failed" if st in FAILED else "unknown"
        s[key] += n
    return s


def for_client(client) -> dict:
    names = list(Msp360Company.objects.filter(client=client).values_list("name", flat=True))
    plans = list(Msp360Plan.objects.filter(company__in=names).select_related("ticket")) if names else []
    plans.sort(key=lambda p: (p.status == 0, p.computer, p.name))
    return {"companies": names, "plans": plans, "computers": list(Msp360Computer.objects.filter(company__in=names)) if names else [],
            "failed": sum(1 for p in plans if p.is_failure)}
