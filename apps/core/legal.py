"""Legal texts shown on invoices, quotes, the client portal and to staff — all editable in Settings › Legal & terms.

Texts are plain writing with a little formatting: a line starting "## " is a heading, "- " is a bullet, a blank line
starts a new paragraph. {placeholders} are filled in when shown, so the late fee, state and company details always
match your other settings.

Which state's law applies follows the client's office: clients in Texas get Texas (El Paso County); everyone else,
including clients with no address, gets Arizona (Maricopa County). Both counties can be changed in Settings.

These are starting drafts for your business, not legal advice — have them reviewed before relying on them.
"""
import hashlib
import re

from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe

from .models import Setting

from .legal_texts import DOCS, RELEASED  # noqa: F401 — re-exported


def jurisdiction(client=None) -> tuple[str, str]:
    """(state, county) whose law governs, following the client's office: Texas clients get Texas, everyone else Arizona."""
    az = (Setting.get("legal.az_county", "") or Setting.get("billing.contract_county", "") or "Maricopa").strip()
    tx = (Setting.get("legal.tx_county", "") or "El Paso").strip()
    if client is not None:
        where = " ".join(filter(None, [getattr(client, "state", ""), getattr(client, "city", ""), getattr(client, "address", ""), getattr(client, "zip", "")]))
        if re.search(r"(^|[\s,])(TX|Tex\.?|Texas)([\s,.]|$)", where, re.I) or re.match(r"^\s*(TX|Texas)\s*$", getattr(client, "state", "") or "", re.I):
            return "Texas", tx
    return "Arizona", az


def text(key: str) -> str:
    saved = Setting.get(f"legal.{key}", "")
    return saved if saved.strip() else DOCS[key][1]


def version(key: str) -> str:
    """Changes whenever the text (or, for the handbook, its link) changes — that's what triggers re-agreeing."""
    extra = Setting.get("legal.handbook_url", "") if key == "handbook_ack" else ""
    return hashlib.sha256((text(key) + "\n" + extra).encode()).hexdigest()[:12]


def updated(key: str) -> str:
    return Setting.get(f"legal.{key}.updated", "") or RELEASED


def values(client=None, key: str = "") -> dict:
    from datetime import date
    state, county = jurisdiction(client)
    company = Setting.get("company.name", "") or "Weststar MSP"
    try:
        from apps.billing.documents import late_policy
        late = late_policy() or "Balances not paid by the due date may be charged a late fee."
    except Exception:  # noqa: BLE001
        late = ""
    try:
        upd = date.fromisoformat(updated(key)).strftime("%B %-d, %Y") if key else ""
    except ValueError:
        upd = updated(key)
    pct = Setting.get("billing.quote_deposit_pct", "") or "0"
    handbook = Setting.get("legal.handbook_url", "")
    return {
        "company": company, "company_upper": company.upper(), "state": state, "county": county,
        "company_address": (Setting.get("company.address", "") or "").replace("\n", ", "),
        "company_phone": Setting.get("company.phone", ""), "support_email": Setting.get("company.email", "") or Setting.get("email.support_address", ""),
        "billing_email": Setting.get("company.billing_email", "") or Setting.get("company.email", ""),
        "late_policy": late, "dispute_days": Setting.get("legal.dispute_days", "") or "10", "suspend_days": Setting.get("legal.suspend_days", "") or "30",
        "quote_valid_days": Setting.get("billing.quote_valid_days", "") or "30",
        "deposit_line": (f"A deposit of {pct.rstrip('0').rstrip('.') if '.' in pct else pct}% is due when you accept this quote." if pct not in ("", "0", "0.0", "0.00")
                         else "No deposit is required unless shown on the quote."),
        "handbook_where": f" (available at {handbook})" if handbook else "",
        "updated": upd, "today": timezone.localdate().strftime("%B %-d, %Y"),
    }


def render_text(key: str, client=None) -> str:
    v = values(client, key)
    return re.sub(r"\{([a-z_]+)\}", lambda m: str(v.get(m.group(1), m.group(0))), text(key))


def to_html(raw: str) -> str:
    """## headings, - bullets, blank-line paragraphs. Everything else is escaped."""
    out, para, items = [], [], []

    def flush():
        if para:
            out.append("<p>" + "<br>".join(escape(x) for x in para) + "</p>")
            para.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{escape(x)}</li>" for x in items) + "</ul>")
            items.clear()
    for line in (raw or "").splitlines():
        s = line.strip()
        if not s:
            flush()
        elif s.startswith("## "):
            flush()
            out.append(f"<h3>{escape(s[3:])}</h3>")
        elif s.startswith("- "):
            if para:
                flush()
            items.append(s[2:])
        else:
            if items:
                flush()
            para.append(s)
    flush()
    return mark_safe("".join(out))  # noqa: S308 — every piece above is escaped


def html(key: str, client=None) -> str:
    return to_html(render_text(key, client))


def title(key: str) -> str:
    return DOCS[key][0]


# ── Acceptances ──
def needs(person, key: str, every_days: int | None = None) -> bool:
    """True if this staff user / portal user hasn't agreed to the current version (or did so too long ago)."""
    from .models import LegalAcceptance
    f = {"doc": key}
    f["portal_user" if person.__class__.__name__ == "PortalUser" else "user"] = person
    last = LegalAcceptance.objects.filter(**f).order_by("-accepted_at").first()
    if last is None or last.version != version(key):
        return True
    return bool(every_days) and (timezone.now() - last.accepted_at).days >= every_days


def accept(person, key: str, request=None, signed_name: str = ""):
    from .models import LegalAcceptance
    from .net import client_ip
    f = {"portal_user" if person.__class__.__name__ == "PortalUser" else "user": person}
    return LegalAcceptance.objects.create(doc=key, version=version(key), signed_name=signed_name[:200],
                                          ip=client_ip(request)[:45] if request else "", **f)


def staff_due(user) -> list[str]:
    """Which staff agreements this person still needs to accept."""
    from django.conf import settings
    due = []
    if not getattr(settings, "LEGAL_GATES", True) or Setting.get("legal.staff_gate", "true") == "false":
        return due
    months = int(Setting.get("legal.staff_ack_months", "") or 12)
    if needs(user, "staff_confidentiality", every_days=months * 365 // 12 if months else None):
        due.append("staff_confidentiality")
    if needs(user, "handbook_ack"):
        due.append("handbook_ack")
    return due


# ── Workplace notices (Employee portal) ──
# Official sources only. Physical posters are still required at each office; this page is the electronic copy for
# remote and traveling staff. Thresholds use Settings › Legal & terms › Number of employees.
NOTICES = [
    # (group, title, agency, who it applies to, link, condition)
    ("Federal", "Employee Rights Under the Fair Labor Standards Act (minimum wage)", "U.S. Department of Labor, Wage & Hour", "All employers", "https://www.dol.gov/general/topics/posters", ""),
    ("Federal", "Employee Polygraph Protection Act", "U.S. Department of Labor, Wage & Hour", "All employers", "https://www.dol.gov/general/topics/posters", ""),
    ("Federal", "Your Rights Under USERRA (military service)", "U.S. Department of Labor, VETS", "All employers", "https://www.dol.gov/general/topics/posters", ""),
    ("Federal", "\"Know Your Rights\": Workplace Discrimination is Illegal", "U.S. Equal Employment Opportunity Commission", "Employers with 15 or more employees", "https://www.eeoc.gov/poster", "15"),
    ("Federal", "Employee Rights Under the Family and Medical Leave Act", "U.S. Department of Labor, Wage & Hour", "Employers with 50 or more employees", "https://www.dol.gov/general/topics/posters", "50"),
    ("Federal", "Job Safety and Health: It's the Law (OSHA) — Texas office", "U.S. Department of Labor, OSHA", "Private employers (Arizona uses its own ADOSH poster below)", "https://www.dol.gov/general/topics/posters", ""),
    ("Arizona", "Minimum Wage (current year)", "Industrial Commission of Arizona", "All Arizona employers", "https://www.azica.gov/posters-employers-must-display", ""),
    ("Arizona", "Earned Paid Sick Time", "Industrial Commission of Arizona", "All Arizona employers", "https://www.azica.gov/posters-employers-must-display", ""),
    ("Arizona", "Employee Safety and Health Protection (ADOSH)", "Industrial Commission of Arizona, ADOSH", "All Arizona employers", "https://www.azica.gov/posters-employers-must-display", ""),
    ("Arizona", "Work Exposure to Bodily Fluids; Work Exposure to MRSA, Spinal Meningitis or Tuberculosis", "Industrial Commission of Arizona, Claims", "All Arizona employers", "https://www.azica.gov/posters-employers-must-display", ""),
    ("Arizona", "Discrimination in Employment (Arizona Civil Rights Act)", "Arizona Attorney General, Civil Rights Division", "Arizona employers", "https://www.azcommerce.com/small-business/checklist-items/having-employees-and-job-training-programs/required-workplace-posters/", ""),
    ("Arizona", "Unemployment Insurance — information for employees", "Arizona Department of Economic Security", "Employers covered by Arizona unemployment insurance", "https://www.azcommerce.com/small-business/checklist-items/having-employees-and-job-training-programs/required-workplace-posters/", ""),
    ("Texas", "Texas Unemployment Compensation Act and Texas Payday Law", "Texas Workforce Commission", "Employers liable for Texas unemployment tax", "https://www.twc.texas.gov/sites/default/files/fdcm/docs/texas-unemployment-compensation-act-and-texas-payday-law-poster-twc.pdf", ""),
    ("Texas", "Reporting Workplace Violence (English/Español)", "Texas Workforce Commission / Department of Public Safety", "All Texas employers with one or more employees", "https://www.twc.texas.gov/sites/default/files/fdcm/docs/workplace-violence-poster-twc.pdf", ""),
    ("Texas", "Notice of Workers' Compensation Coverage (or No Coverage)", "Texas Department of Insurance", "All Texas employers — must say whether you have coverage", "https://www.tdi.texas.gov/forms/form20employer.html", ""),
    ("Texas", "Employer's Notice of Ombudsman Program", "Office of Injured Employee Counsel", "Texas employers with workers' compensation coverage", "https://www.oiec.texas.gov/news/employernotice.html", "wc"),
    ("Texas", "Earned Income Tax Credit notice (by March 1 each year)", "Texas Workforce Commission / IRS", "All Texas employers", "https://www.twc.texas.gov/employer-resources/earned-income-tax-credit-notification", ""),
]


def notices() -> list[dict]:
    try:
        n = int(Setting.get("legal.employee_count", "") or 0)
    except ValueError:
        n = 0
    wc = Setting.get("legal.tx_workers_comp", "yes") != "no"
    out = []
    for group, ttl, agency, who, link, cond in NOTICES:
        applies = True
        if cond.isdigit():
            applies = n >= int(cond) if n else True
        elif cond == "wc":
            applies = wc
        out.append({"group": group, "title": ttl, "agency": agency, "who": who, "link": link, "applies": applies})
    return out


def portal_gate_on() -> bool:
    from django.conf import settings
    return getattr(settings, "LEGAL_GATES", True) and Setting.get("legal.portal_gate", "true") != "false"
