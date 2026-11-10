"""Settings › Speed & server health — measures this server so slowness can be pinned down from the browser."""
import os
import shutil
import time
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.db import connection
from django.db.models import Avg, Count, Max
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import JobRun, OutboxEmail, SlowRequest
from .permissions import can

# What the same tests take on a normal small server (2 vCPU, 4 GB). Used to say "about N× slower than normal".
REFERENCE = {"cpu_ms": 150, "db_ping_ms": 0.3, "tickets_ms": 25, "invoices_ms": 15}


def _meminfo() -> dict:
    out = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                out[k] = int(v.strip().split()[0]) * 1024
    except OSError:
        pass
    # Inside Docker the container may have its own limit (cgroup v2).
    try:
        with open("/sys/fs/cgroup/memory.max") as f:
            lim = f.read().strip()
        with open("/sys/fs/cgroup/memory.current") as f:
            cur = int(f.read().strip())
        if lim.isdigit():
            out["CgroupLimit"], out["CgroupUsed"] = int(lim), cur
    except OSError:
        pass
    return out


def _gb(n) -> str:
    return f"{n / 1024 ** 3:.1f} GB" if n is not None else "—"


def _time(fn, repeat=1) -> float:
    a = time.perf_counter()
    for _ in range(repeat):
        fn()
    return (time.perf_counter() - a) * 1000 / repeat


def measure() -> dict:
    from apps.billing.models import Invoice
    from apps.helpdesk import queries
    from apps.helpdesk.models import Ticket

    def cpu():
        x = 0
        for i in range(2_000_000):
            x += i * i % 7
        return x

    def ping():
        with connection.cursor() as c:
            c.execute("SELECT 1")
            c.fetchone()

    def tickets():
        qs = Ticket.objects.filter(merged_into__isnull=True).order_by("-updated_at")
        try:
            qs = queries.with_extras(qs)
        except Exception:  # noqa: BLE001
            pass
        list(qs[:50])
        qs.count()

    def invoices():
        list(Invoice.objects.select_related("client").order_by("-id")[:50])

    ping(), tickets(), invoices()  # warm up, so the numbers show steady speed rather than the first-load cost
    res = {"cpu_ms": _time(cpu), "db_ping_ms": _time(ping, 20), "tickets_ms": _time(tickets), "invoices_ms": _time(invoices)}
    res["slower"] = {k: (v / REFERENCE[k]) for k, v in res.items() if k in REFERENCE}
    return res


def _db_facts() -> dict:
    facts = {}
    try:
        with connection.cursor() as c:
            c.execute("SELECT pg_size_pretty(pg_database_size(current_database())), split_part(version(), ' ', 2)")
            facts["size"], facts["version"] = c.fetchone()
            c.execute("SELECT count(*), count(*) FILTER (WHERE state = 'active' AND now() - query_start > interval '5 seconds') "
                      "FROM pg_stat_activity WHERE datname = current_database()")
            facts["connections"], facts["long_queries"] = c.fetchone()
            c.execute("SELECT count(*) FROM pg_locks WHERE NOT granted")
            facts["waiting_locks"] = c.fetchone()[0]
    except Exception as e:  # noqa: BLE001
        facts["error"] = str(e)[:200]
    return facts


def health_page(request):
    if request.method == "POST" and can(request.user, "admin", "manage"):
        if request.POST.get("action") == "clear":
            SlowRequest.objects.all().delete()
            messages.success(request, "Slow page list cleared.")
        return redirect("/settings/health/")
    cpus = os.cpu_count() or 1
    try:
        load = os.getloadavg()
    except OSError:
        load = (0, 0, 0)
    mem = _meminfo()
    total, avail = mem.get("MemTotal"), mem.get("MemAvailable")
    swap_used = (mem.get("SwapTotal", 0) - mem.get("SwapFree", 0)) if mem else 0
    media = getattr(settings, "MEDIA_ROOT", "/") or "/"
    try:
        disk = shutil.disk_usage(media if os.path.exists(media) else "/")
    except OSError:
        disk = None
    speed = measure()
    db = _db_facts()
    since = timezone.now() - timedelta(hours=24)
    slow = SlowRequest.objects.all()[:50]
    top = (SlowRequest.objects.filter(created_at__gte=since).values("method", "path")
           .annotate(n=Count("id"), avg=Avg("total_ms"), worst=Max("total_ms"), db=Avg("db_ms")).order_by("-n")[:8])

    findings = []
    if load[0] > cpus * 1.5:
        findings.append(("bad", f"The server's processor is overloaded (load {load[0]:.1f} on {cpus} CPU{'s' if cpus > 1 else ''}). Something is using all the CPU — check for other sites or programs on this server, or move to a bigger server."))
    if total and avail is not None and avail < total * 0.1:
        findings.append(("bad", f"The server is nearly out of memory ({_gb(avail)} free of {_gb(total)}). Add memory or move other programs off this server."))
    if swap_used > 256 * 1024 ** 2:
        findings.append(("warn", f"{_gb(swap_used)} of memory has been pushed to disk (swap). That makes everything slow; more memory fixes it."))
    if mem.get("CgroupLimit") and mem["CgroupUsed"] > mem["CgroupLimit"] * 0.9:
        findings.append(("bad", "This app is at the memory limit Docker gave it."))
    if speed["slower"]["cpu_ms"] > 3:
        findings.append(("warn", f"The processor is about {speed['slower']['cpu_ms']:.0f}× slower than a normal small server. Shared or burstable servers (e.g. the cheapest plans) slow down when their CPU credits run out."))
    if speed["db_ping_ms"] > 5:
        findings.append(("bad", f"Each database question takes {speed['db_ping_ms']:.1f} ms (normal is under 1 ms). A page asks 20–50 of them, so this alone adds seconds. Is the database on another server or a slow disk?"))
    if db.get("long_queries"):
        findings.append(("warn", f"{db['long_queries']} database quer{'y has' if db['long_queries'] == 1 else 'ies have'} been running for over 5 seconds right now."))
    if db.get("waiting_locks"):
        findings.append(("warn", f"{db['waiting_locks']} database request{'s are' if db['waiting_locks'] != 1 else ' is'} waiting on another to finish."))
    if disk and disk.free < disk.total * 0.05:
        findings.append(("bad", f"The disk is almost full ({_gb(disk.free)} free)."))
    pending = OutboxEmail.objects.filter(status="pending").count()
    if pending > 20:
        findings.append(("warn", f"{pending} emails are waiting to go out — check Settings › Email sending."))
    failed_jobs = list(JobRun.objects.filter(last_ok=False).values_list("name", flat=True))
    if not findings:
        findings.append(("good", "Nothing on the server looks overloaded right now. If pages are slow, the slow page list below shows which ones and whether the time went to the database or the app."))

    return render(request, "core/health.html", {
        "server": {"cpus": cpus, "load": load, "mem_total": _gb(total), "mem_free": _gb(avail), "swap_used": _gb(swap_used),
                   "container": (f"{_gb(mem['CgroupUsed'])} of {_gb(mem['CgroupLimit'])}" if mem.get("CgroupLimit") else ""),
                   "disk_free": _gb(disk.free) if disk else "—", "disk_total": _gb(disk.total) if disk else "—",
                   "workers": os.environ.get("WEB_WORKERS", "3"), "version": settings.APP_VERSION},
        "speed": speed, "ref": REFERENCE, "db": db, "findings": findings, "slow": slow, "top": top,
        "slow_ms": getattr(settings, "SLOW_REQUEST_MS", 1000), "pending": pending, "failed_jobs": failed_jobs,
        "can_manage": can(request.user, "admin", "manage"),
    })
