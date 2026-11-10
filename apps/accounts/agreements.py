"""Staff agreements at sign-in: confidentiality & acceptable use (yearly) and the handbook acknowledgment."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.core import legal
from apps.core.audit import audit
from apps.core.models import Setting


@login_required
def agreements(request):
    due = legal.staff_due(request.user)
    nxt = request.GET.get("next", "/")
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = "/"
    error = ""
    if request.method == "POST" and due:
        name = request.POST.get("signed_name", "").strip()
        missing = [k for k in due if request.POST.get(f"agree_{k}") != "1"]
        if len(name) < 3:
            error = "Type your full name to sign."
        elif missing:
            error = "Tick each box to agree."
        else:
            for k in due:
                legal.accept(request.user, k, request, signed_name=name)
            audit(request, "agree", "user", request.user.pk, "Agreed to " + ", ".join(legal.title(k) for k in due), area="hr")
            request.session["legal_checked"] = 0
            messages.success(request, "Thank you — your agreement is saved in your HR file.")
            return redirect(nxt)
    if not due:
        return redirect(nxt)
    docs = [{"key": k, "title": legal.title(k), "html": legal.html(k)} for k in due]
    return render(request, "accounts/agreements.html", {"docs": docs, "error": error, "handbook_url": Setting.get("legal.handbook_url", "")})
