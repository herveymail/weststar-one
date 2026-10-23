from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.core.permissions import can
from apps.core.views import module_list

from .models import Employee

MY_TABS = [("pto", "Time off"), ("timeclock", "Timeclock"), ("mileage", "Mileage")]
ADMIN_TABS = [("employees", "Employees"), ("timeclock", "Timeclock"), ("pto", "Time off requests")]


@login_required
def my_hr(request):
    tab = request.GET.get("tab", "pto")
    if tab not in dict(MY_TABS):
        tab = "pto"
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
