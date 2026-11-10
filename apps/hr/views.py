from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.core.permissions import can
from apps.core.views import module_list

from .models import Employee

MY_TABS = [("pto", "Time off"), ("timeclock", "Timeclock"), ("mileage", "Mileage"), ("notices", "Workplace notices"), ("agreements", "My agreements")]
ADMIN_TABS = [("employees", "Employees"), ("timeclock", "Timeclock"), ("pto", "Time off requests"), ("agreements", "Agreements")]


@login_required
def my_hr(request):
    tab = request.GET.get("tab", "pto")
    if tab not in dict(MY_TABS):
        tab = "pto"
    if request.headers.get("HX-Request") and tab in ("notices", "agreements"):
        return _legal_tab(request, tab)
    if request.headers.get("HX-Request"):
        # Always only the signed-in person's own rows here, even for H/R managers.
        return module_list(request, tab, embedded_filter={"user_id": request.user.pk}, template="core/_module_table.html")
    emp = Employee.objects.filter(user=request.user, archived_at__isnull=True).first()
    return render(request, "hr/my_hr.html", {"tabs": MY_TABS, "tab": tab, "emp": emp})


@login_required
def hr_admin(request):
    if not can(request.user, "hr"):
        raise PermissionDenied
    tab = request.GET.get("tab", "employees")
    if tab not in dict(ADMIN_TABS):
        tab = "employees"
    if tab == "agreements":
        return _agreements_admin(request)
    return module_list(request, tab, extra={"page_tabs": ADMIN_TABS, "page_tab": tab, "page_title": "H/R Admin", "page_tab_base": "/hr/"})


@login_required
@require_POST
def clock(request):
    """Top-bar Clock in / Clock out for the signed-in person."""
    from django.utils import timezone

    from apps.core.audit import audit
    from apps.core.views import refresh

    from .models import TimeclockEntry

    open_entry = TimeclockEntry.objects.filter(user=request.user, status="Open", clock_out__isnull=True, archived_at__isnull=True).order_by("-clock_in").first()
    if open_entry:
        open_entry.clock_out = timezone.now()
        open_entry.status = "Submitted"
        open_entry.save()
        audit(request, "clock_out", "timeclock", open_entry.pk, "Clocked out", area="hr")
        messages.success(request, "Clocked out.")
    else:
        e = TimeclockEntry.objects.create(user=request.user, clock_in=timezone.now(), status="Open", created_by=request.user)
        audit(request, "clock_in", "timeclock", e.pk, "Clocked in", area="hr")
        messages.success(request, "Clocked in.")
    return refresh()


def _legal_tab(request, tab):
    """My HR › Workplace notices / My agreements."""
    from apps.core import legal
    from apps.core.models import Setting
    if tab == "notices":
        emp = Employee.objects.filter(user=request.user, archived_at__isnull=True).first()
        office = (emp.office if emp else "") or ""
        first = "Texas" if office == "El Paso" else "Arizona" if office == "Phoenix" else ""
        groups = {}
        for n in legal.notices():
            groups.setdefault(n["group"], []).append(n)
        order = ["Federal"] + ([first] if first else []) + [g for g in ("Arizona", "Texas") if g != first]
        return render(request, "hr/_notices.html", {"groups": [(g, groups.get(g, [])) for g in order], "office": office,
                                                    "count": Setting.get("legal.employee_count", "")})
    mine = request.user.legal_acceptances.all()[:50]
    docs = [{"key": k, "title": legal.title(k), "html": legal.html(k), "last": next((a for a in mine if a.doc == k), None),
             "current": legal.version(k)} for k in ("staff_confidentiality", "handbook_ack")]
    return render(request, "hr/_agreements.html", {"docs": docs, "mine": mine, "handbook_url": Setting.get("legal.handbook_url", "")})


def _agreements_admin(request):
    """H/R Admin › Agreements: who has signed the current staff agreements, and when."""
    from apps.accounts.models import User
    from apps.core import legal
    from apps.core.models import LegalAcceptance
    keys = ["staff_confidentiality", "handbook_ack"]
    versions = {k: legal.version(k) for k in keys}
    rows = []
    for u in User.objects.filter(is_active=True).order_by("name"):
        last = {k: LegalAcceptance.objects.filter(user=u, doc=k).order_by("-accepted_at").first() for k in keys}
        rows.append({"u": u, "cells": [(last[k], bool(last[k] and last[k].version == versions[k])) for k in keys]})
    return render(request, "hr/agreements_admin.html", {"rows": rows, "titles": [legal.title(k) for k in keys],
                                                        "page_tabs": ADMIN_TABS, "page_tab": "agreements"})
