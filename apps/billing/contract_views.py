"""Billing › Contracts: the agreement builder, the agreement page, and its PDF.

/billing/contract/build/           new agreement (MSA or Managed Services) — pick, fill in, the wording is written for you
/billing/contract/<pk>/build/      change the details of a draft and rebuild the wording
/billing/contract/<pk>/            the agreement as the client sees it, with Send for e-signature and the signed record
/billing/contract/<pk>/pdf/        PDF (with the signature page once signed)
"""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string

from apps.core import legal
from apps.core.audit import audit
from apps.core.models import Setting
from apps.core.permissions import can
from apps.crm.models import Client

from . import contract_builder as builder
from . import contract_texts as T
from .models import Contract, contract_link


KIND_NAMES = {"MSA": "Master Services Agreement", "Managed": "Managed Services Agreement", "Break/fix": "Hourly Services Agreement",
              "BAA": "Business Associate Agreement"}


class BuildForm(forms.ModelForm):
    kind = forms.ChoiceField(choices=[("Managed", "Managed services (MSP) contract"), ("Break/fix", "Hourly services (break/fix) contract"),
                                      ("MSA", "Master Services Agreement (MSA) only"), ("BAA", "Business Associate Agreement (BAA, for HIPAA clients)")])
    services = forms.MultipleChoiceField(choices=[], required=False, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Contract
        fields = ["client", "name", "start_date", "term_months", "renewal_months", "auto_renew", "notice_days", "increase_pct", "include_msa", "msa",
                  "users", "user_rate", "workstations", "workstation_rate", "servers", "server_rate", "flat_fee", "setup_fee", "included_hours",
                  "overage_rate", "after_hours_rate", "trip_fee", "service_notes", "extra_charges", "exclusions", "our_signer", "our_title"]
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), "service_notes": forms.Textarea(attrs={"rows": 3}),
                   "exclusions": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *a, user=None, **kw):
        super().__init__(*a, **kw)
        self.fields["client"].queryset = Client.objects.filter(archived_at__isnull=True).order_by("name")
        self.fields["name"].required = False
        self.fields["services"].choices = [(k, n) for k, n, _d in T.all_services()]
        self.fields["extra_charges"].widget = forms.Textarea(attrs={"rows": 3, "placeholder": "VoIP phones (8): 240\nAlarm monitoring: 45"})
        cid = (self.data.get("client") or self.initial.get("client") or (self.instance.client_id if self.instance.pk else None)) or 0
        self.fields["msa"].queryset = Contract.objects.filter(client_id=cid, type="MSA", archived_at__isnull=True).exclude(status__in=["Cancelled", "Expired"]).exclude(pk=self.instance.pk or 0)
        self.fields["msa"].empty_label = "— none —"
        for name, f in self.fields.items():
            w = f.widget
            if isinstance(w, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                continue
            w.attrs.setdefault("class", "select" if isinstance(w, forms.Select) else "textarea" if isinstance(w, forms.Textarea) else "input")
            if isinstance(f, forms.DecimalField):
                w.attrs.setdefault("inputmode", "decimal")

    def clean(self):
        d = super().clean()
        if d.get("kind") == "Managed":
            if not (d.get("services") or (d.get("service_notes") or "").strip()):
                self.add_error("services", "Pick at least one service that is covered.")
            bad = builder.bad_charge_lines(d.get("extra_charges"))
            if bad:
                self.add_error("extra_charges", f"Couldn't read the amount on: “{bad[0][:60]}”. Write what it is, a colon, then the monthly amount — e.g. VoIP phones (8): 240")
            priced = bool(builder._CHARGE and [1 for ln in (d.get("extra_charges") or "").splitlines() if builder._CHARGE.match(ln.strip())]) or any((d.get(q) and d.get(r)) for q, r in (("users", "user_rate"), ("workstations", "workstation_rate"), ("servers", "server_rate"))) or d.get("flat_fee")
            if not priced:
                self.add_error("flat_fee", "Add a price: a count and a rate (users, computers or servers), or a base monthly fee.")
        if d.get("kind") == "Break/fix" and not d.get("overage_rate"):
            self.add_error("overage_rate", "Add the hourly rate.")
        if d.get("msa") and d.get("include_msa"):
            d["include_msa"] = False   # already under a signed MSA: don't attach the terms a second time
        if d.get("kind") in ("MSA", "BAA"):
            d["include_msa"], d["msa"] = False, None
        return d


def _defaults(request, client=None) -> dict:
    def dec(key):
        v = (Setting.get(key, "") or "").strip()
        return v or None
    msa = Contract.objects.filter(client=client, type="MSA", status="Active", archived_at__isnull=True).first() if client else None
    return {"kind": "Managed", "client": client.pk if client else None, "term_months": int(Setting.get("billing.contract_months", "") or 12), "auto_renew": Setting.get("billing.contract_auto_renew", "true") != "false",
            "notice_days": 30, "services": T.SERVICE_DEFAULTS, "overage_rate": (client.hourly_rate if client and client.hourly_rate else dec("billing.hourly_rate")),
            "after_hours_rate": dec("billing.afterhours_rate"), "our_signer": request.user.name, "our_title": getattr(request.user, "title", "") or "",
            "include_msa": msa is None, "msa": msa.pk if msa else None}


@login_required
def build(request, pk=None):
    if not can(request.user, "billing", "edit"):
        raise PermissionDenied
    c = get_object_or_404(Contract.objects.select_related("client"), pk=pk, archived_at__isnull=True) if pk else None
    if c and (c.signed or c.status in ("Active", "Expired", "Cancelled")):
        messages.error(request, "This agreement is signed or closed, so its details can't be changed. Make a new agreement instead.")
        return redirect(f"/billing/contract/{c.pk}/")
    client = Client.objects.filter(pk=request.GET.get("client_id") or 0).first()
    if request.method == "POST":
        form = BuildForm(request.POST, instance=c, user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            d = form.cleaned_data
            obj.type, obj.services = d["kind"], d["services"]
            obj.include_msa = d.get("include_msa", False)
            obj.msa = d.get("msa")
            if not obj.name:
                obj.name = KIND_NAMES[obj.type] + f" — {obj.client.name}"
            if not obj.pk:
                from apps.core.numbering import next_number
                obj.number, obj.status, obj.created_by = next_number("contract"), "Draft", request.user
            builder.build(obj)
            audit(request, "update" if c else "create", "contracts", obj.pk, f"{'Rebuilt' if c else 'Built'} agreement {obj.name}", area="billing")
            messages.success(request, "Agreement built. Read it through, then send it for e-signature.")
            return redirect(f"/billing/contract/{obj.pk}/")
    else:
        init = {"kind": c.type if c.type in KIND_NAMES else "Managed", "services": c.services} if c else _defaults(request, client)
        if not c and request.GET.get("kind") in KIND_NAMES:
            init["kind"] = request.GET["kind"]
        form = BuildForm(instance=c, initial=init, user=request.user)
    return render(request, "billing/contract_build.html", {"form": form, "c": c,                                                            "services": [(k, n, d.replace("{unlimited}", "Unlimited r")) for k, n, d in T.all_services()], "exclusions": T.EXCLUSIONS},
                  status=422 if request.method == "POST" else 200)


def doc_context(c, for_pdf=False) -> dict:
    """What the agreement page and the PDF both show."""
    from apps.core.branding import login_brand, logo_url
    state, county = legal.jurisdiction(c.client)
    sig = c.signatures.order_by("-created_at").first()
    lines = builder.price_lines(c) if c.built and c.type == "Managed" else []
    return {**login_brand(), "c": c, "client": c.client, "company": Setting.get("company.name", "") or "Weststar MSP", "logo_url": logo_url(),
            "scope_html": legal.to_html(c.scope), "terms_html": legal.to_html(c.terms), "signature": sig, "price_lines": lines,
            "law": "" if c.built else f"This agreement is governed by the laws of the State of {state}" + (f"; any dispute will be heard in {county} County, {state}." if county else "."),
            "for_pdf": for_pdf}


@login_required
def page(request, pk):
    if not can(request.user, "billing"):
        raise PermissionDenied
    c = get_object_or_404(Contract.objects.select_related("client", "msa"), pk=pk)
    return render(request, "billing/contract_page.html", {**doc_context(c), "link": contract_link(c) if c.status != "Cancelled" else "",
                                                          "kind_name": KIND_NAMES.get(c.type, c.type),
                                                          "can_bill": c.type == "Managed" and c.built and c.status == "Active" and can(request.user, "billing", "edit"),
                                                          "bill_todo": (not c.recurring_id and builder.monthly_total(c) > 0) or (not c.setup_invoice_id and bool(c.setup_fee)),
                                                          "can_edit": can(request.user, "billing", "edit"), "editable": not c.signed and c.status in ("Draft", "Sent"),
                                                          "schedules": c.schedules.filter(archived_at__isnull=True) if c.type == "MSA" else []})


@login_required
def billing(request, pk):
    """Signed managed-services contract → the recurring monthly invoice and a draft invoice for the onboarding fee."""
    if request.method != "POST" or not can(request.user, "billing", "edit"):
        raise PermissionDenied
    c = get_object_or_404(Contract.objects.select_related("client"), pk=pk, archived_at__isnull=True)
    if c.type != "Managed" or not c.built or c.status != "Active":
        messages.error(request, "Billing is set up from a signed managed services contract.")
        return redirect(f"/billing/contract/{c.pk}/")
    made = builder.create_billing(c, request.user)
    bits = []
    if made.get("recurring"):
        r = made["recurring"]
        bits.append(f"a recurring invoice of ${r.total:,.2f} a month, first one on {r.next_run:%b %-d, %Y}")
    if made.get("invoice"):
        bits.append(f"draft invoice {made['invoice'].number} for the onboarding fee")
    if bits:
        audit(request, "create", "contracts", c.pk, f"Set up billing from {c.name}: " + " and ".join(bits), area="billing")
        messages.success(request, "Created " + " and ".join(bits) + ".")
    else:
        messages.info(request, "Billing for this contract is already set up.")
    return redirect(f"/billing/contract/{c.pk}/")


def pdf_bytes(c) -> bytes:
    import logging
    for name in ("fontTools", "weasyprint"):
        logging.getLogger(name).setLevel(logging.WARNING)
    from weasyprint import HTML
    from weasyprint.urls import URLFetcher
    from apps.portal.views import _contract_hash
    ctx = doc_context(c, for_pdf=True)
    ctx["fingerprint"] = _contract_hash(c)
    ctx["intact"] = bool(ctx["signature"]) and ctx["signature"].content_hash == ctx["fingerprint"]
    html = render_to_string("billing/contract_pdf.html", ctx)
    return HTML(string=html, base_url=None, url_fetcher=URLFetcher(allowed_protocols={"data"}, allow_redirects=False)).write_pdf()


def pdf_response(c) -> HttpResponse:
    r = HttpResponse(pdf_bytes(c), content_type="application/pdf")
    safe = "".join(ch if ch.isalnum() else "-" for ch in (c.number or c.name))[:60].strip("-")
    r["Content-Disposition"] = f'attachment; filename="Agreement-{safe}.pdf"'
    r["Cache-Control"] = "private, no-store"
    return r


@login_required
def pdf(request, pk):
    if not can(request.user, "billing"):
        raise PermissionDenied
    return pdf_response(get_object_or_404(Contract.objects.select_related("client"), pk=pk))
