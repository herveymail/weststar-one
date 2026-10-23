"""Copies everything from the old PHP Weststar One (MariaDB/MySQL) into the new database.

* Safe to re-run. Every imported row keeps its old id in ``legacy_id``; running again updates it
  instead of making a duplicate. Run it as often as you like while both systems are in use.
* Never overwrites your work: a record changed in the new app since it was imported is left alone
  (counted as "kept"). Existing staff keep their role, active status, password and two-factor.
* Ticket, invoice, quote, contract and project numbers stay exactly as they were, and the number
  counters are moved past them so new numbers never clash.
* Secrets (2FA seeds, Wi-Fi passwords, ISP accounts, H/R SSN and bank fields) are decrypted with the
  OLD keys and re-encrypted with the new APP_ENCRYPTION_KEY. Plaintext never touches disk.
* Old bcrypt password hashes are kept, so nobody needs a reset; each one is upgraded to Argon2 the
  first time that person signs in.
* ``dry_run`` does everything inside a transaction and then rolls it back.
"""
import datetime as dt
import json
import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation

from django.db import models, transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.models import (
    BankTransaction, Contract, Expense, Invoice, InvoiceLine, Policy, Quote, QuoteLine, RecurringInvoice,
    RecurringLine, Renewal, TrainingAssignment, Vendor,
)
from apps.core.audit import audit
from apps.core.crypto import encrypt
from apps.core.models import Counter
from apps.crm.models import Asset, Client, ClientNote, Contact, Network, Project
from apps.helpdesk.models import Queue, Ticket, TicketMessage, TimeEntry
from apps.hr.models import Employee, TimeclockEntry, TimeOffRequest
from apps.sales.models import Campaign, Lead
from apps.tools.models import CalendarEvent, Domain, InventoryItem, KbArticle, MileageTrip, SecureMessage, Workflow

from .crypto import LegacyDecryptError, decrypt_net_secret, decrypt_setting, decrypt_value
from .models import ImportRun

TICKET_STATUS = {
    "new": "New", "open": "Open", "in_progress": "Open", "pending": "Waiting on client", "on_hold": "Waiting on client",
    "waiting": "Waiting on client", "waiting_on_client": "Waiting on client", "waiting_on_vendor": "Waiting on vendor",
    "scheduled": "Scheduled", "resolved": "Resolved", "closed": "Closed", "cancelled": "Closed",
}


# ── value cleaners ──
def title(v, allowed, fallback):
    s = re.sub(r"[_-]+", " ", str(v or "").strip().lower())
    return next((a for a in allowed if a.lower() == s), fallback)


def s(v, n=500):
    return None if v is None or v == "" else str(v)[:n]


def txt(v):
    return None if v is None else (v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v))


def num(v):
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation:
        return None


def int_(v):
    try:
        return None if v is None or v == "" else int(Decimal(str(v)))
    except (InvalidOperation, ValueError):
        return None


def yes(v):
    return v in (1, "1", True, b"\x01")


def day(v):
    if v in (None, ""):
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    t = str(v)[:10]
    try:
        d = dt.date.fromisoformat(t)
    except ValueError:
        return None
    return d if d.year > 1900 else None


def ts(v):
    """Old app stored UTC-ish naive datetimes; treat them as UTC."""
    if v in (None, ""):
        return None
    if not isinstance(v, dt.datetime):
        try:
            v = dt.datetime.fromisoformat(str(v).replace(" ", "T"))
        except ValueError:
            return None
    if v.year < 1971:
        return None
    return v if timezone.is_aware(v) else v.replace(tzinfo=dt.timezone.utc)


def email(v):
    t = str(v or "").strip()
    return t[:254] if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", t) else None


def url(v):
    t = str(v or "").strip()
    if not t:
        return None
    return (t if re.match(r"^https?://", t, re.I) else "https://" + t)[:500]


def number_tail(v) -> int:
    m = re.search(r"(\d+)\s*$", str(v or ""))
    return int(m.group(1)) if m else 0


@dataclass
class Step:
    name: str
    source: int = 0
    imported: int = 0
    kept: int = 0
    skipped: int = 0
    warnings: list = field(default_factory=list)


class DryRunDone(Exception):
    pass


class Importer:
    def __init__(self, conn, app_key: str = "", encryption_key: str = "", log=print, uploads_dir: str | None = None):
        self.conn, self.app_key, self.enc_key, self.log = conn, app_key or "", encryption_key or "", log
        self.uploads_dir = uploads_dir
        self.dry_run = False
        self.ids: dict[str, dict[int, int]] = {}
        self.steps: list[Step] = []
        self._tables = None

    # ── reading the old database (a live connection, or a DumpSource from an uploaded backup) ──
    def has(self, table):
        if hasattr(self.conn, "has"):
            return self.conn.has(table)
        if self._tables is None:
            with self.conn.cursor() as c:
                c.execute("SHOW TABLES")
                self._tables = {r[0] if isinstance(r, tuple) else list(r.values())[0] for r in c.fetchall()}
        return table in self._tables

    def read(self, table, order):
        if not self.has(table):
            return []
        if hasattr(self.conn, "read"):
            return self.conn.read(table, order)
        import MySQLdb.cursors
        with self.conn.cursor(MySQLdb.cursors.DictCursor) as c:
            if not (re.fullmatch(r"[a-z_]+", table) and re.fullmatch(r"[a-z_]+", order)):
                raise ValueError("bad table name")
            c.execute(f"SELECT * FROM `{table}` ORDER BY `{order}`")  # noqa: S608 — names are constants in this file
            return list(c.fetchall())

    def ref(self, kind, v):
        if v in (None, "", 0, "0"):
            return None
        try:
            return self.ids.get(kind, {}).get(int(v))
        except (TypeError, ValueError):
            return None

    def secret(self, fn, warnings, what):
        try:
            v = fn()
        except (LegacyDecryptError, ValueError):
            if not (self.app_key or self.enc_key):
                warnings.append(f"Couldn't unlock {what}: add the old config.php (or its two keys) and import again")
            else:
                warnings.append(f"Couldn't unlock {what} with the keys given: make sure they're from the same old server")
            return None
        return encrypt(v) if v else None

    # ── writing ──
    @staticmethod
    def _clean(model, values: dict) -> dict:
        """Fit values to the model: '' for empty text, cut text to length, valid choices only."""
        out = {}
        for k, v in values.items():
            f = model._meta.get_field(k)
            name = f.attname if f.is_relation else k
            if isinstance(f, (models.CharField, models.TextField)) and not f.null:
                v = "" if v is None else str(v)
                if f.max_length:
                    v = v[: f.max_length]
            if isinstance(f, (models.BooleanField,)) and v is None:
                v = False
            if isinstance(f, (models.PositiveIntegerField, models.IntegerField)) and v is None and not f.null:
                v = f.default if f.has_default() else 0
            out[name] = v
        return out

    def upsert(self, kind, model, rows, legacy_key, map_row, name=None):
        step = Step(name or kind, source=len(rows))
        self.ids.setdefault(kind, {})
        has_imported_at = any(f.name == "imported_at" for f in model._meta.fields)
        for r in rows:
            v = map_row(r, step.warnings)
            if v is None:
                step.skipped += 1
                continue
            lid = int(r[legacy_key])
            created_at = v.pop("created_at", None)
            updated_at = v.pop("updated_at", None)
            archived = v.pop("_archived", None)
            secrets = v.pop("_secrets", {})
            data = self._clean(model, v)
            obj = model.objects.filter(legacy_id=lid).first()
            if obj and has_imported_at and obj.imported_at and obj.updated_at and obj.updated_at > obj.imported_at:
                step.kept += 1  # changed in the new app since import: leave it alone
                self.ids[kind][lid] = obj.pk
                continue
            if obj is None:
                obj = model(legacy_id=lid)
            for k, val in data.items():
                setattr(obj, k, val)
            for k, val in secrets.items():
                if val is not None:
                    setattr(obj, k, val)
            if archived is not None and hasattr(obj, "archived_at"):
                obj.archived_at = (obj.archived_at or timezone.now()) if archived else None
            obj.save()
            stamp = {}
            if created_at:
                stamp["created_at"] = created_at
            if updated_at:
                stamp["updated_at"] = updated_at
            if has_imported_at:
                stamp["imported_at"] = updated_at or F("updated_at")
            if stamp:
                model.objects.filter(pk=obj.pk).update(**stamp)
            self.ids[kind][lid] = obj.pk
            step.imported += 1
        self._done(step)
        return step

    def lines(self, kind, line_model, fk, parent_kind, rows, parent_key, map_row, kept_parents):
        """Replace the line items of each imported parent (skips parents kept because they changed)."""
        step = Step(kind, source=len(rows))
        by_parent: dict[int, list] = {}
        for r in rows:
            pid = self.ref(parent_kind, r.get(parent_key))
            if pid and pid not in kept_parents:
                by_parent.setdefault(pid, []).append(r)
            else:
                step.skipped += 1
        for pid, items in by_parent.items():
            line_model.objects.filter(**{f"{fk}_id": pid}).delete()
            objs = [line_model(**{f"{fk}_id": pid}, **self._clean(line_model, map_row(r))) for r in items]
            for o in objs:  # bulk_create skips save(), so work the line total out here
                o.line_total = (Decimal(o.qty or 0) * Decimal(o.rate or 0)).quantize(Decimal("0.01"))
            line_model.objects.bulk_create(objs)
            step.imported += len(objs)
        self._done(step)

    def _done(self, step: Step):
        self.steps.append(step)
        extra = "".join(f"  ({n} {w})" for n, w in [(step.kept, "kept — changed here"), (step.skipped, "skipped")] if n)
        self.log(f"  {step.name:<18} {step.imported:>6} of {step.source}{extra}")

    def kept_ids(self, model, kind):
        ids = set(self.ids.get(kind, {}).values())
        return set(model.objects.filter(pk__in=ids, imported_at__isnull=False, updated_at__gt=F("imported_at")).values_list("pk", flat=True))

    # ── the import ──
    def run(self, dry_run=False, run=None):
        self.dry_run = dry_run
        run = run or ImportRun.objects.create(dry_run=dry_run)
        try:
            with transaction.atomic():
                self.log("Importing from the old Weststar One…")
                self.users()
                self.crm()
                self.portal()
                self.billing()
                self.payments()
                self.tools()
                self.hr()
                self.tickets()
                self.files()
                self.settings()
                self.bump_counters()
                audit(None, "import", "import", run.pk, f"{'Dry run' if dry_run else 'Import'} from old Weststar One: {sum(x.imported for x in self.steps)} records", area="admin",
                      user=run.requested_by)
                if dry_run:
                    raise DryRunDone
        except DryRunDone:
            pass
        except Exception as e:
            run.finished_at, run.error, run.summary = timezone.now(), str(e)[:2000], [asdict(x) for x in self.steps]
            run.save()
            raise
        run.finished_at, run.summary = timezone.now(), [asdict(x) for x in self.steps]
        run.save()
        return run

    def users(self):
        rows = self.read("users", "user_id")
        step = Step("users", source=len(rows))
        self.ids["users"] = {}
        for r in rows:
            em = email(r.get("user_email"))
            if not em:
                step.skipped += 1
                step.warnings.append(f"user {r['user_id']}: no valid email")
                continue
            lid = int(r["user_id"])
            raw_hash = str(r.get("user_password") or "")
            old_hash = "bcrypt$" + re.sub(r"^\$2[ay]\$", "$2b$", raw_hash) if re.match(r"^\$2[aby]\$", raw_hash) else None
            existing = User.objects.filter(legacy_id=lid).first() or User.objects.filter(email__iexact=em).first()
            if existing:
                # Existing staff keep their role, active status, password and 2FA — only fill blanks.
                changed = []
                if not existing.legacy_id:
                    existing.legacy_id, changed = lid, changed + ["legacy_id"]
                for attr, val in (("title", s(r.get("user_title"), 100)), ("phone", s(r.get("user_phone"), 50))):
                    if val and not getattr(existing, attr):
                        setattr(existing, attr, val)
                        changed.append(attr)
                # Still on the imported old hash? Follow password changes made in the old app.
                untouched = existing.password.startswith("bcrypt$")  # never signed in to the new app
                if old_hash and untouched and existing.password != old_hash:
                    existing.password = old_hash
                    changed.append("password")
                # 2FA seed that couldn't be read last time (old keys added later): fill it in now.
                if untouched and not existing.mfa_enabled and not existing.totp_secret_enc and r.get("user_totp_secret") and yes(r.get("user_2fa_enabled")):
                    seed = self.secret(lambda: decrypt_setting(str(r["user_totp_secret"]), self.app_key), [], f"2FA seed for {em}")
                    if seed:
                        existing.totp_secret_enc, existing.mfa_enabled = seed, True
                        changed += ["totp_secret_enc", "mfa_enabled"]
                if changed:
                    existing.save(update_fields=changed + ["updated_at"])
                User.objects.filter(pk=existing.pk).update(imported_at=timezone.now())
                self.ids["users"][lid] = existing.pk
                step.kept += 1
                continue
            totp = None
            if r.get("user_totp_secret"):
                totp = self.secret(lambda: decrypt_setting(str(r["user_totp_secret"]), self.app_key), [], f"2FA seed for {em}")
            elif r.get("user_2fa_secret"):
                totp = encrypt(str(r["user_2fa_secret"]))
            old_role = str(r.get("user_role") or "")
            role = {"crm": "sales", "hr": "viewer"}.get(old_role, old_role)
            if role not in ("admin", "manager", "help_desk", "tech", "sales", "accounting", "viewer"):
                step.warnings.append(f"{em}: old role '{old_role}' became Tech — check it in Staff users")
                role = "tech"
            u = User(
                email=em.lower(), name=s(r.get("user_name"), 200) or em, role=role,
                hr_access=yes(r.get("user_hr_access")) or role == "admin" or old_role == "hr", title=s(r.get("user_title"), 100) or "",
                phone=s(r.get("user_phone"), 50) or "", is_active=not yes(r.get("user_archived")),
                mfa_enabled=yes(r.get("user_2fa_enabled")) and bool(totp), totp_secret_enc=totp or "",
                must_change_password=yes(r.get("user_force_password_change")), legacy_id=lid,
            )
            if old_hash:
                u.password = old_hash
            else:
                u.set_unusable_password()
                step.warnings.append(f"{em}: password could not be carried over — reset it in Staff users")
            if yes(r.get("user_2fa_enabled")) and not totp:
                step.warnings.append(f"{em}: their 2FA couldn't be carried over"
                                     + (" (add the old config.php and import again to keep it)" if not self.app_key else " (the APP_KEY given doesn't match)")
                                     + "; otherwise they'll set it up again at next sign-in")
            u.last_login = ts(r.get("user_last_login"))
            u.save()
            User.objects.filter(pk=u.pk).update(imported_at=timezone.now())
            self.ids["users"][lid] = u.pk
            step.imported += 1
        self._done(step)

    def crm(self):
        R = self.ref
        self.upsert("clients", Client, self.read("clients", "client_id"), "client_id", lambda r, w: {
            "name": s(r.get("client_name"), 200) or f"Client {r['client_id']}",
            "status": "Former" if yes(r.get("client_archived")) else title(r.get("client_status"), ["Active", "Lead", "Inactive", "Former"], "Active"),
            "type": title(r.get("client_type"), ["Business", "Residential", "Nonprofit", "Government"], "Business"),
            "plan": "Managed" if r.get("client_billing_type") == "managed" or re.search("managed", str(r.get("client_contract_type") or ""), re.I) else "Break/fix" if r.get("client_billing_type") == "hourly" else None,
            "industry": s(r.get("client_industry")), "phone": s(r.get("client_phone")), "email": email(r.get("client_email")), "website": url(r.get("client_website")),
            "address": s(r.get("client_address")), "city": s(r.get("client_city")), "state": s(r.get("client_state")), "zip": s(r.get("client_zip")),
            "account_manager": R("users", r.get("client_account_manager")), "hourly_rate": num(r.get("client_rate")), "tax_rate": num(r.get("client_tax_rate")),
            "net_terms": int_(r.get("client_net_terms")) or 30, "sla_response_hours": int_(r.get("client_sla_response_hours")) or 4,
            "sla_resolution_hours": int_(r.get("client_sla_resolution_hours")) or 24,
            "account_alert": s(r.get("client_alert_note"), 255) or (f"Account flag: {r['client_account_alert']}" if r.get("client_account_alert") not in (None, "", "none") else None),
            "notes": txt(r.get("client_notes")), "_archived": yes(r.get("client_archived")), "created_at": ts(r.get("client_created_at")),
        })

        def contact(r, w):
            cid = R("clients", r.get("contact_client_id"))
            if not cid:
                return None
            return {"client": cid, "name": s(r.get("contact_name"), 200) or "Unnamed", "title": s(r.get("contact_title")), "email": email(r.get("contact_email")),
                    "phone": s(r.get("contact_phone")), "mobile": s(r.get("contact_mobile")), "is_primary": yes(r.get("contact_primary")), "notes": txt(r.get("contact_notes")),
                    "role": title(r.get("contact_role"), ["Decision maker", "Technical", "Billing", "End user", "Other"], "Other"), "_archived": yes(r.get("contact_archived"))}
        self.upsert("contacts", Contact, self.read("contacts", "contact_id"), "contact_id", contact)

        self.upsert("vendors", Vendor, self.read("vendors", "vendor_id"), "vendor_id", lambda r, w: {
            "name": s(r.get("vendor_name")) or "Vendor", "contact_name": s(r.get("vendor_contact_name")), "email": email(r.get("vendor_email")),
            "phone": s(r.get("vendor_phone")), "website": url(r.get("vendor_website")), "notes": txt(r.get("vendor_notes")),
            "_secrets": {"account_number": encrypt(str(r["vendor_account_number"])) if r.get("vendor_account_number") else None},
        })

        def asset(r, w):
            cid = R("clients", r.get("asset_client_id"))
            if not cid:
                return None
            return {"client": cid, "name": s(r.get("asset_name")) or "Asset", "type": title(r.get("asset_type"), ["Workstation", "Laptop", "Server", "Network", "Printer", "Mobile", "Other"], "Other"),
                    "status": title(r.get("asset_status"), ["Active", "Storage", "RMA", "Retired"], "Active"), "make": s(r.get("asset_make")), "model": s(r.get("asset_model")),
                    "serial": s(r.get("asset_serial")), "os": s(r.get("asset_os")), "ip": s(r.get("asset_ip")), "mac": s(r.get("asset_mac")),
                    "purchase_date": day(r.get("asset_purchase_date")), "warranty_expires": day(r.get("asset_warranty_expires") or r.get("asset_warranty_expire")),
                    "notes": txt(r.get("asset_notes")), "_archived": yes(r.get("asset_archived"))}
        self.upsert("assets", Asset, self.read("assets", "asset_id"), "asset_id", asset)

        def network(r, w):
            cid = R("clients", r.get("network_client_id"))
            if not cid:
                return None
            notes = [txt(r.get("network_notes")),
                     r.get("network_firewall_model") and f"Firewall: {r['network_firewall_model']} {r.get('network_firewall_ip') or ''}".strip(),
                     r.get("network_switch_model") and f"Switch: {r['network_switch_model']} {r.get('network_switch_ip') or ''}".strip()]
            return {"client": cid, "name": s(r.get("network_domain")) or "Office network", "subnet": s(r.get("network_subnet") or r.get("network_lan_range")),
                    "gateway": s(r.get("network_gateway")), "dns": ", ".join(x for x in [r.get("network_dns_primary"), r.get("network_dns_secondary")] if x) or None,
                    "isp": s(r.get("network_isp_name")), "wifi_ssid": s(r.get("network_wifi_ssid")), "notes": "\n".join(x for x in notes if x) or None,
                    "_secrets": {
                        "isp_account": self.secret(lambda: decrypt_net_secret(r.get("network_isp_account"), self.enc_key), w, "ISP account"),
                        "wifi_password": self.secret(lambda: decrypt_net_secret(r.get("network_wifi_password"), self.enc_key), w, "Wi-Fi password"),
                    }}
        self.upsert("networks", Network, self.read("client_networks", "network_id"), "network_id", network)

        def note(r, w):
            cid = R("clients", r.get("note_client_id"))
            if not cid:
                return None
            body = txt(r.get("note_content")) or ""
            return {"client": cid, "title": (body.split("\n")[0] or "Note")[:120], "body": body, "created_by": R("users", r.get("note_user_id")), "created_at": ts(r.get("note_created_at"))}
        self.upsert("client_notes", ClientNote, self.read("client_notes", "note_id"), "note_id", note, "client notes")

        self.upsert("projects", Project, self.read("projects", "project_id"), "project_id", lambda r, w: {
            "number": s(r.get("project_number"), 30), "name": s(r.get("project_name")) or "Project", "client": R("clients", r.get("project_client_id")),
            "owner": R("users", r.get("project_owner_id")),
            "status": title(r.get("project_status"), ["Planning", "In progress", "On hold", "Complete", "Cancelled"], "Complete" if r.get("project_completed_at") else "Planning"),
            "start_date": day(r.get("project_start_date")), "due_date": day(r.get("project_due_date")), "budget_hours": num(r.get("project_budget_hours")),
            "billable": yes(r.get("project_billable")), "description": txt(r.get("project_description")), "created_at": ts(r.get("project_created_at")),
        })
        self.upsert("leads", Lead, self.read("leads", "lead_id"), "lead_id", lambda r, w: {
            "company": s(r.get("lead_company")) or "Lead", "contact_name": s(r.get("lead_contact_name")), "email": email(r.get("lead_email")), "phone": s(r.get("lead_phone")),
            "stage": title(r.get("lead_stage"), ["New", "Contacted", "Qualified", "Proposal", "Negotiation", "Won", "Lost"], "New"), "source": s(r.get("lead_source")),
            "value": num(r.get("lead_value") or r.get("lead_estimated_value")), "next_followup": day(r.get("lead_next_followup")),
            "assigned_to": R("users", r.get("lead_assigned_to")), "notes": txt(r.get("lead_notes")),
        })
        self.upsert("campaigns", Campaign, self.read("email_campaigns", "campaign_id"), "campaign_id", lambda r, w: {
            "name": s(r.get("campaign_name")) or "Campaign", "type": "Email", "subject": s(r.get("campaign_subject")), "body": txt(r.get("campaign_body")),
            "status": title(r.get("campaign_status"), ["Draft", "Scheduled", "Active", "Sent", "Paused"], "Draft"),
            "send_date": day(r.get("campaign_sent_at") or r.get("campaign_scheduled_at")),
        })

    def billing(self):
        R = self.ref

        def invoice(r, w):
            cid = R("clients", r.get("invoice_client_id"))
            if not cid:
                return None
            st = str(r.get("invoice_status") or "")
            total, tax = num(r.get("invoice_total")) or Decimal(0), num(r.get("invoice_tax_amount")) or Decimal(0)
            sub = num(r.get("invoice_subtotal"))
            return {"number": s(r.get("invoice_number"), 30), "client": cid,
                    "status": "Void" if st in ("cancelled", "voided") else title(st, ["Draft", "Sent", "Viewed", "Partial", "Paid", "Overdue", "Void"], "Draft"),
                    "invoice_date": day(r.get("invoice_date")) or dt.date(2000, 1, 1), "due_date": day(r.get("invoice_due_date")) or day(r.get("invoice_date")) or dt.date(2000, 1, 1),
                    "tax_rate": num(r.get("invoice_tax_rate")), "subtotal": sub if sub and sub > 0 else total - tax, "tax_amount": tax, "total": total,
                    "amount_paid": num(r.get("invoice_amount_paid")) or Decimal(0), "scope": txt(r.get("invoice_scope")), "notes": txt(r.get("invoice_notes")),
                    "created_at": ts(r.get("invoice_created_at"))}
        self.upsert("invoices", Invoice, self.read("invoices", "invoice_id"), "invoice_id", invoice)
        self.lines("invoice lines", InvoiceLine, "invoice", "invoices", self.read("invoice_items", "item_id"), "item_invoice_id", lambda r: {
            "description": s(r.get("item_description")) or "—", "qty": num(r.get("item_qty")) or Decimal(1), "rate": num(r.get("item_rate")) or Decimal(0),
            "taxable": yes(r.get("item_tax")), "sort_order": int_(r.get("item_sort_order")) or 0,
        }, self.kept_ids(Invoice, "invoices"))

        def recurring(r, w):
            cid = R("clients", r.get("recurring_client_id"))
            if not cid:
                return None
            f = str(r.get("recurring_frequency") or "monthly")
            return {"name": (s(r.get("recurring_scope"), 200) or "Recurring invoice").split("\n")[0], "client": cid,
                    "frequency": "Year" if re.search("year|annual", f) else "Quarter" if "quarter" in f else "Month",
                    "next_run": day(r.get("recurring_next_date")) or timezone.localdate(),
                    "status": "Active" if re.search("active", str(r.get("recurring_status") or "active"), re.I) else "Paused",
                    "tax_rate": num(r.get("recurring_tax_rate")), "subtotal": num(r.get("recurring_subtotal")) or Decimal(0),
                    "total": num(r.get("recurring_subtotal")) or Decimal(0), "notes": txt(r.get("recurring_scope"))}
        self.upsert("recurring", RecurringInvoice, self.read("recurring_invoices", "recurring_id"), "recurring_id", recurring)
        self.lines("recurring lines", RecurringLine, "schedule", "recurring", self.read("recurring_invoice_items", "ri_item_id"), "ri_recurring_id", lambda r: {
            "description": s(r.get("ri_description")) or "—", "qty": num(r.get("ri_qty")) or Decimal(1), "rate": num(r.get("ri_rate")) or Decimal(0),
            "taxable": True, "sort_order": int_(r.get("ri_sort")) or 0,
        }, self.kept_ids(RecurringInvoice, "recurring"))

        def quote(r, w):
            cid = R("clients", r.get("quote_client_id"))
            if not cid:
                return None
            sub, total = num(r.get("quote_subtotal")), num(r.get("quote_total")) or Decimal(0)
            return {"number": s(r.get("quote_number"), 30), "client": cid, "status": title(r.get("quote_status"), ["Draft", "Sent", "Accepted", "Declined", "Invoiced"], "Draft"),
                    "quote_date": day(r.get("quote_date")) or dt.date(2000, 1, 1), "expires_on": day(r.get("quote_expire_date")), "tax_rate": num(r.get("quote_tax_rate")),
                    "subtotal": sub if sub and sub > 0 else total, "total": total, "scope": txt(r.get("quote_scope")), "notes": txt(r.get("quote_notes"))}
        self.upsert("quotes", Quote, self.read("quotes", "quote_id"), "quote_id", quote)
        self.lines("quote lines", QuoteLine, "quote", "quotes", self.read("quote_items", "qi_id"), "qi_quote_id", lambda r: {
            "description": s(r.get("qi_description")) or "—", "qty": num(r.get("qi_quantity")) or Decimal(1), "rate": num(r.get("qi_rate")) or Decimal(0),
            "taxable": True if r.get("qi_taxable") is None else yes(r.get("qi_taxable")), "sort_order": int_(r.get("qi_sort_order")) or 0,
        }, self.kept_ids(Quote, "quotes"))

        def contract(r, w):
            cid = R("clients", r.get("contract_client_id"))
            if not cid:
                return None
            st = str(r.get("contract_status") or "")
            return {"number": s(r.get("contract_number"), 30), "name": s(r.get("contract_name") or r.get("contract_title")) or "Contract", "client": cid,
                    "type": title(r.get("contract_type"), ["Managed", "Break/fix", "Project", "BAA", "NDA", "Other"], "Other"),
                    "status": "Cancelled" if st == "voided" else title(st, ["Draft", "Sent", "Active", "Expired", "Cancelled"], "Draft"),
                    "start_date": day(r.get("contract_start_date")), "end_date": day(r.get("contract_end_date")), "auto_renew": yes(r.get("contract_auto_renew")),
                    "monthly_rate": num(r.get("contract_recurring_amount") or r.get("contract_monthly_rate")), "included_hours": num(r.get("contract_included_hours")),
                    "overage_rate": num(r.get("contract_overage_rate")), "scope": txt(r.get("contract_scope")), "terms": txt(r.get("contract_terms"))}
        self.upsert("contracts", Contract, self.read("contracts", "contract_id"), "contract_id", contract)
        self.upsert("policies", Policy, self.read("client_policies", "cp_id"), "cp_id", lambda r, w: {
            "name": s(r.get("cp_name")) or "Policy", "client": R("clients", r.get("cp_client_id")), "version": s(r.get("cp_version")),
            "status": "Current" if r.get("cp_signed_at") else title(r.get("cp_status"), ["Draft", "Current", "Review due", "Retired"], "Draft"),
            "next_review": day(r.get("cp_review_date")),
        })
        courses = {str(c.get("tc_key") or c.get("tc_id")): str(c.get("tc_name")) for c in self.read("training_courses", "tc_id")}

        def training(r, w):
            cid = R("clients", r.get("te_client_id"))
            if not cid:
                return None
            raw = txt(r.get("te_courses")) or "[]"
            try:
                items = json.loads(raw)
                items = items if isinstance(items, list) else [items]
            except ValueError:
                items = raw.split(",")
            names = [courses.get(str(k).strip(), str(k).strip()) for k in items if str(k).strip()]
            return {"course": ", ".join(names)[:200] or "Security training", "client": cid, "due_date": day(r.get("te_due_date")),
                    "status": "Complete" if re.search("complete", str(r.get("te_status")), re.I) else "In progress"}
        self.upsert("training", TrainingAssignment, self.read("training_enrollments", "te_id"), "te_id", training)
        self.upsert("renewals", Renewal, self.read("warranties", "warranty_id"), "warranty_id", lambda r, w: {
            "item": s(r.get("warranty_name")) or "Warranty", "client": R("clients", r.get("warranty_client_id")),
            "type": title(r.get("warranty_type"), ["License", "Domain", "Warranty", "Contract", "Subscription", "Other"], "Warranty"),
            "renews_on": day(r.get("warranty_end_date")) or dt.date(2000, 1, 1), "cost": num(r.get("warranty_cost")), "notes": txt(r.get("warranty_notes")),
        })
        cats = {int(c["category_id"]): str(c.get("category_name")) for c in self.read("expense_categories", "category_id")}
        self.upsert("expenses", Expense, self.read("expenses", "expense_id"), "expense_id", lambda r, w: {
            "spent_on": day(r.get("expense_date")) or dt.date(2000, 1, 1), "vendor": R("vendors", r.get("expense_vendor_id")),
            "category": cats.get(int_(r.get("expense_category_id")) or 0), "amount": num(r.get("expense_amount")) or Decimal(0),
            "client": R("clients", r.get("expense_client_id")), "billable": bool(r.get("expense_client_id")), "description": s(r.get("expense_description")),
        })
        self.upsert("banking", BankTransaction, self.read("bank_transactions", "btxn_id"), "btxn_id", lambda r, w: {
            "posted_on": day(r.get("btxn_date")) or dt.date(2000, 1, 1), "description": s(r.get("btxn_description")) or "—", "amount": num(r.get("btxn_amount")) or Decimal(0),
            "match_status": "Matched" if r.get("btxn_matched_invoice_id") or r.get("btxn_expense_id") else "Ignored" if r.get("btxn_status") == "ignored" else "Unmatched",
            "invoice": R("invoices", r.get("btxn_matched_invoice_id")), "notes": s(r.get("btxn_match_note")),
        }, "bank transactions")

    def tools(self):
        R = self.ref

        def event(r, w):
            starts = ts(r.get("event_start"))
            if not starts:
                return None
            return {"title": s(r.get("event_title")) or "Event", "starts_at": starts, "ends_at": ts(r.get("event_end")), "client": R("clients", r.get("event_client_id")),
                    "notes": txt(r.get("event_description"))}
        self.upsert("calendar", CalendarEvent, self.read("calendar_events", "event_id"), "event_id", event)
        self.upsert("inventory", InventoryItem, self.read("inventory_items", "inv_id"), "inv_id", lambda r, w: {
            "name": s(r.get("inv_name")) or "Item", "sku": s(r.get("inv_sku")), "on_hand": int_(r.get("inv_qty_on_hand")) or 0, "reorder_at": int_(r.get("inv_reorder_point")),
            "cost": num(r.get("inv_unit_cost")), "price": num(r.get("inv_unit_price")), "location": s(r.get("inv_location")),
            "notes": txt(r.get("inv_notes") or r.get("inv_description")), "_archived": yes(r.get("inv_archived")),
        })

        def trip(r, w):
            uid = R("users", r.get("mile_user_id"))
            if not uid:
                w.append(f"mileage {r['mile_id']}: no matching staff user")
                return None
            return {"trip_date": day(r.get("mile_date")) or dt.date(2000, 1, 1),
                    "trip": " → ".join(str(x) for x in [r.get("mile_from"), r.get("mile_to")] if x)[:300] or s(r.get("mile_purpose")) or "Trip",
                    "miles": num(r.get("mile_distance")) or Decimal(0), "client": R("clients", r.get("mile_client_id")), "billable": bool(r.get("mile_client_id")), "user": uid}
        self.upsert("mileage", MileageTrip, self.read("hr_mileage", "mile_id"), "mile_id", trip)

        def message(r, w):
            cid = R("clients", r.get("msg_client_id"))
            if not cid:
                return None
            out = r.get("msg_direction") != "inbound"
            return {"client": cid, "subject": s(r.get("msg_subject")) or "(no subject)", "direction": "Outbound" if out else "Inbound",
                    "status": "Archived" if yes(r.get("msg_archived")) else "Read" if yes(r.get("msg_read")) else "Unread",
                    "portal_user": R("portal_users", r.get("msg_portal_user_id")), "author": R("users", r.get("msg_staff_user_id") or r.get("msg_user_id")),
                    "client_read_at": ts(r.get("msg_read_at")) if out else None,
                    "_secrets": {"body": encrypt(txt(r["msg_body"])) if r.get("msg_body") else None}, "created_at": ts(r.get("msg_created_at"))}
        msgs = self.read("secure_messages", "msg_id")
        self.upsert("messages", SecureMessage, msgs, "msg_id", message, "secure messages")
        for r in msgs:
            root = R("messages", r.get("msg_thread_id"))
            if root and str(r.get("msg_thread_id")) != str(r["msg_id"]):
                SecureMessage.objects.filter(legacy_id=int(r["msg_id"])).update(thread_id=root)
        certs = self.read("certificates", "cert_id")
        today = timezone.localdate()

        def domain(r, w):
            name = str(r.get("domain_name") or "").lower()
            c = next((x for x in certs if str(x.get("cert_domain") or "").lower() == name), None)
            exp = day((c or {}).get("cert_live_expiry") or (c or {}).get("cert_expire_date"))
            ssl = "Unknown" if not exp else "Expired" if exp < today else "Expiring" if exp < today + dt.timedelta(days=30) else "Valid"
            return {"name": s(r.get("domain_name"), 253) or "domain", "client": R("clients", r.get("domain_client_id")), "registrar": s(r.get("domain_registrar")),
                    "expires_on": day(r.get("domain_whois_expiry") or r.get("domain_expire_date")), "dns_provider": s(r.get("domain_dns_provider")),
                    "ssl_status": ssl, "ssl_expires_on": exp, "notes": txt(r.get("domain_notes"))}
        self.upsert("domains", Domain, self.read("domains", "domain_id"), "domain_id", domain)
        kbc = {int(c["kbc_id"]): str(c.get("kbc_name")) for c in self.read("kb_categories", "kbc_id")}
        self.upsert("kb", KbArticle, self.read("kb_articles", "kb_id"), "kb_id", lambda r, w: {
            "title": s(r.get("kb_title")) or "Article", "category": kbc.get(int_(r.get("kb_category_id")) or 0),
            "visibility": "Portal" if yes(r.get("kb_portal_visible")) else "Staff only", "views": int_(r.get("kb_views")) or 0, "body": txt(r.get("kb_content")),
            "_archived": yes(r.get("kb_archived")),
        }, "knowledge base")
        self.upsert("workflows", Workflow, self.read("workflow_rules", "wr_id"), "wr_id", lambda r, w: {
            "name": s(r.get("wr_name")) or "Workflow", "trigger": "Ticket created", "action": "Send email",
            "conditions": "\n".join(x for x in [f"Imported from old workflow (trigger: {r.get('wr_trigger') or '?'})", txt(r.get("wr_conditions")), txt(r.get("wr_actions"))] if x),
            "status": "Paused", "runs": int_(r.get("wr_run_count")) or 0,
        })

    def hr(self):
        R = self.ref
        emps = self.read("hr_employees", "emp_id")

        def employee(r, w):
            def dec(col, what):
                return self.secret(lambda: decrypt_value(str(r[col]), self.enc_key), w, what) if r.get(col) else None
            where = str(r.get("emp_city") or r.get("emp_department") or "")
            return {"name": " ".join(x for x in [r.get("emp_first_name"), r.get("emp_last_name")] if x) or "Employee", "user": R("users", r.get("emp_user_id")),
                    "title": s(r.get("emp_position")), "office": "Phoenix" if re.search("phoenix", where, re.I) else "El Paso" if re.search("el paso", where, re.I) else None,
                    "status": title(r.get("emp_status"), ["Active", "Onboarding", "On leave", "Terminated"], "Active"), "hire_date": day(r.get("emp_hire_date")),
                    "email": email(r.get("emp_email")), "phone": s(r.get("emp_phone")),
                    "pay_type": title(r.get("emp_pay_type"), ["Hourly", "Salary"], "Hourly") if r.get("emp_pay_type") else None,
                    "pto_balance_hours": num(r.get("emp_pto_balance")),
                    "emergency_contact": " · ".join(str(x) for x in [r.get("emp_emergency_name"), r.get("emp_emergency_phone"), r.get("emp_emergency_relation")] if x) or None,
                    "_secrets": {"ssn": dec("emp_ssn_enc", "SSN"), "bank_routing": dec("emp_bank_routing_enc", "bank routing #"), "bank_account": dec("emp_bank_account_enc", "bank account #")}}
        self.upsert("employees", Employee, emps, "emp_id", employee)
        emp_user = {int(e["emp_id"]): R("users", e.get("emp_user_id")) for e in emps}
        pto = [dict(r, _uid=emp_user.get(int_(r.get("pto_emp_id")) or 0)) for r in self.read("hr_pto_requests", "pto_id")]
        pto += [dict(r, _uid=R("users", r.get("pto_user_id")), pto_id=1_000_000 + int(r["pto_id"])) for r in self.read("hr_pto", "pto_id")]

        def time_off(r, w):
            if not r["_uid"]:
                return None
            start = day(r.get("pto_start_date")) or dt.date(2000, 1, 1)
            return {"user": r["_uid"], "kind": title(r.get("pto_type"), ["Vacation", "Sick", "Personal", "Unpaid"], "Vacation"), "starts_on": start,
                    "ends_on": day(r.get("pto_end_date")) or start, "hours": num(r.get("pto_hours")) or Decimal(0),
                    "status": title(r.get("pto_status"), ["Pending", "Approved", "Denied"], "Pending"), "reason": s(r.get("pto_notes") or r.get("pto_reason"))}
        self.upsert("pto", TimeOffRequest, pto, "pto_id", time_off, "time off")

        def clock(r, w):
            uid = R("users", r.get("tc_user_id")) or emp_user.get(int_(r.get("tc_employee_id")) or 0)
            t_in = ts(r.get("tc_clock_in"))
            if not uid or not t_in:
                return None
            return {"user": uid, "clock_in": t_in, "clock_out": ts(r.get("tc_clock_out")),
                    "status": "Approved" if yes(r.get("tc_approved")) else "Submitted" if r.get("tc_clock_out") else "Open", "notes": s(r.get("tc_notes"))}
        self.upsert("timeclock", TimeclockEntry, self.read("hr_timeclock", "tc_id"), "tc_id", clock)

    def payments(self):
        """Payments (checks, online and AutoPay), the Stripe account keys, and each client's card on file at Stripe."""
        from apps.billing.models import AutoPayLink, Invoice, Payment
        from apps.core.models import Setting

        from .crypto import decrypt_setting_value
        R = self.ref
        # Stripe keys (payment_gateways) — only filled if not set here
        for g in (self.read("payment_gateways", "gateway_id") if self.has("payment_gateways") else []):
            if str(g.get("gateway_type")) != "stripe" or not yes(g.get("gateway_enabled")):
                continue
            for col, key, secret in (("gateway_public_key", "stripe.publishable_key", False), ("gateway_secret_key", "stripe.secret_key", True),
                                     ("gateway_webhook_secret", "stripe.webhook_secret", True)):
                raw = str(g.get(col) or "")
                try:
                    val = decrypt_setting_value(raw, self.app_key) if raw.startswith("enc1:") else raw
                except LegacyDecryptError:
                    val = ""
                if raw.startswith("enc1:") and not self.app_key:
                    val = ""
                if val and not Setting.get(key, ""):
                    Setting.put(key, val, secret=secret)
                elif raw and not val:
                    self.log(f"  (Stripe {col.split('_')[1]} key couldn't be unlocked — add the old config.php, or paste it in Settings › Payments)")
        # Cards on file (stay at Stripe; only the ids and last 4 come across)
        clients = self.read("clients", "client_id")
        step = Step("autopay cards", source=sum(1 for r in clients if r.get("client_stripe_customer_id")))
        for r in clients:
            cid = R("clients", r.get("client_id"))
            cus = str(r.get("client_stripe_customer_id") or "")
            if not cid or not cus:
                continue
            c = Client.objects.get(pk=cid)
            if c.stripe_customer_id and c.stripe_customer_id != cus:
                step.kept += 1
                continue
            pm = str(r.get("client_autopay_payment_method") or "")
            Client.objects.filter(pk=cid).update(
                stripe_customer_id=cus, autopay_enabled=yes(r.get("client_autopay_enabled")) and bool(pm), autopay_method_id=pm,
                autopay_method_type="us_bank_account" if pm.startswith("ba_") or str(r.get("client_autopay_card_brand") or "").lower() in ("ach", "bank", "us_bank_account") else ("card" if pm else ""),
                autopay_brand=s(r.get("client_autopay_card_brand"), 30) or "", autopay_last4=s(r.get("client_autopay_card_last4"), 4) or "",
                autopay_enrolled_at=ts(r.get("client_autopay_enrolled_at")), autopay_last_attempt_at=ts(r.get("client_autopay_last_attempt_at")),
                autopay_last_status=s(r.get("client_autopay_last_status"), 20) or "", autopay_last_error=s(r.get("client_autopay_last_error"), 255) or "")
            step.imported += 1
        self._done(step)
        # Payments — written directly so the imported paid totals stay exactly as they were
        rows = self.read("payments", "payment_id") if self.has("payments") else []
        step = Step("payments", source=len(rows))
        touched = set()
        for r in rows:
            inv = R("invoices", r.get("payment_invoice_id"))
            amt = num(r.get("payment_amount"))
            if not inv or not amt:
                step.skipped += 1
                continue
            lid = int(r["payment_id"])
            m = str(r.get("payment_method") or "").lower()
            source = {"autopay": "autopay", "online": "online"}.get(str(r.get("payment_source") or ""), "staff")
            method = ("Check" if "check" in m else "Cash" if "cash" in m else "Trade account" if "trade" in m else
                      "Bank account (ACH)" if re.search("ach|bank", m) else "Card" if re.search("card|stripe|online|autopay", m) or source != "staff" else "Other")
            status = "Refunded" if yes(r.get("payment_reversed")) else "Succeeded"
            data = {"client_id": Invoice.objects.filter(pk=inv).values_list("client_id", flat=True).first(), "invoice_id": inv, "amount": amt,
                    "method": method, "paid_on": day(r.get("payment_date")) or day(r.get("payment_created_at")) or dt.date(2000, 1, 1),
                    "reference": (s(r.get("payment_reference"), 255) or s(r.get("payment_txn_id"), 255) or ""), "status": status, "source": source,
                    "stripe_payment_intent": (str(r.get("payment_txn_id") or "") if str(r.get("payment_txn_id") or "").startswith("pi_") else "")[:64],
                    "receipt_url": (s(r.get("payment_receipt_url"), 500) or ""), "note": s(r.get("payment_note"), 255) or "",
                    "archived_at": ts(r.get("payment_voided_at")), "created_by_id": R("users", r.get("payment_recorded_by")),
                    "created_at": ts(r.get("payment_created_at")) or timezone.now(), "imported_at": timezone.now()}
            if not Payment.objects.filter(legacy_id=lid).update(**data):
                Payment.objects.bulk_create([Payment(legacy_id=lid, **data)])
            touched.add(inv)
            step.imported += 1
        # whatever the old app counted as paid beyond its payment records stays counted
        from django.db.models import Q, Sum
        for inv in Invoice.objects.filter(Q(pk__in=touched) | Q(legacy_id__isnull=False, amount_paid__gt=0)):
            got = inv.payments.filter(archived_at__isnull=True, status="Succeeded").aggregate(s=Sum("amount"))["s"] or Decimal(0)
            Invoice.objects.filter(pk=inv.pk).update(paid_outside=max(Decimal(0), (inv.amount_paid or 0) - got))
        self._done(step)
        for r in (self.read("autopay_links", "link_id") if self.has("autopay_links") else []):
            pass  # old setup links are one-use and short-lived; new ones are sent from the client page
        _ = AutoPayLink

    def portal(self):
        """Portal groups and the people who sign in to the client portal (their old passwords keep working)."""
        from apps.portal.models import PortalGroup, PortalUser
        R = self.ref
        perms = {"billing": "billing", "contracts": "contracts", "assets": "assets", "submit_tickets": "submit_tickets",
                 "all_tickets": "all_tickets", "messages": "send_messages", "kb": "kb", "policies": "policies"}
        groups = self.read("portal_groups", "pg_id") if self.has("portal_groups") else []
        for r in groups:  # match by name so the 5 standard groups made here aren't doubled
            PortalGroup.objects.filter(name__iexact=str(r.get("pg_name") or ""), legacy_id__isnull=True).update(legacy_id=int(r["pg_id"]))

        def group(r, w):
            def flag(k):
                return yes(r.get(f"pg_can_view_{perms[k]}", r.get(f"pg_can_{perms[k]}")))
            return {"name": s(r.get("pg_name"), 200) or f"Group {r['pg_id']}", "description": s(r.get("pg_description"), 255),
                    **{f"can_{k}": flag(k) for k in perms}}
        self.upsert("portal_groups", PortalGroup, groups, "pg_id", group, "portal groups")
        users = self.read("portal_users", "portal_user_id") if self.has("portal_users") else []
        for r in users:
            em = email(r.get("portal_email"))
            if em:
                PortalUser.objects.filter(email__iexact=em, legacy_id__isnull=True).update(legacy_id=int(r["portal_user_id"]))

        def user(r, w):
            em, cid = email(r.get("portal_email")), R("clients", r.get("portal_client_id"))
            if not em or not cid:
                w.append(f"portal user {r['portal_user_id']}: {'no client' if em else 'no valid email'}")
                return None
            if PortalUser.objects.filter(email__iexact=em).exclude(legacy_id=int(r["portal_user_id"])).exists():
                w.append(f"portal user {em}: that email is already used by another portal account")
                return None
            raw_hash = str(r.get("portal_password") or "")
            pw = "bcrypt$" + re.sub(r"^\$2[ay]\$", "$2b$", raw_hash) if re.match(r"^\$2[aby]\$", raw_hash) else ""

            def flag(k):
                v = r.get(f"portal_can_view_{perms[k]}", r.get(f"portal_can_{perms[k]}"))
                return yes(v)
            contact = R("contacts", r.get("portal_contact_id"))
            if not contact:
                from apps.crm.models import Contact
                contact = Contact.objects.filter(client_id=cid, email__iexact=em).values_list("pk", flat=True).first()
            return {"client": cid, "contact": contact, "name": s(r.get("portal_name"), 200) or em.split("@")[0], "email": em, "password": pw,
                    "role": "admin" if "admin" in (str(r.get("portal_role") or ""), str(r.get("portal_admin_role") or "")) else "standard",
                    "group": R("portal_groups", r.get("portal_group_id")), "is_active": yes(r.get("portal_active")),
                    "last_login": ts(r.get("portal_last_login")), **{f"can_{k}": flag(k) for k in perms},
                    "created_at": ts(r.get("portal_created_at"))}
        self.upsert("portal_users", PortalUser, users, "portal_user_id", user, "portal users")

    def queues(self):
        rows = self.read("ticket_queues", "tq_id") if self.has("ticket_queues") else []
        for r in rows:
            Queue.objects.filter(name__iexact=str(r.get("tq_name") or ""), legacy_id__isnull=True).update(legacy_id=int(r["tq_id"]))

        def queue(r, w):
            color = str(r.get("tq_color") or "")
            return {"name": s(r.get("tq_name"), 80) or f"Queue {r['tq_id']}", "description": s(r.get("tq_description"), 255),
                    "color": color if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else "#2c5cc5", "sla_enabled": yes(r.get("tq_sla")),
                    "keywords": txt(r.get("tq_keywords")) or "", "portal_label": s(r.get("tq_portal_label"), 120),
                    "is_default": yes(r.get("tq_is_default")), "active": yes(r.get("tq_active")), "sort": int_(r.get("tq_sort")) or 0}
        self.upsert("queues", Queue, rows, "tq_id", queue, "ticket queues")
        for r in rows:  # escalation targets need every queue first
            if r.get("tq_escalate_to"):
                Queue.objects.filter(legacy_id=int(r["tq_id"])).update(escalate_to_id=self.ref("queues", r["tq_escalate_to"]))

    def tickets(self):
        R = self.ref
        self.queues()
        rows = self.read("tickets", "ticket_id")

        def ticket(r, w):
            return {"number": s(r.get("ticket_number"), 30) or f"T-{r['ticket_id']}", "subject": s(r.get("ticket_subject"), 255) or "(no subject)",
                    "details": txt(r.get("ticket_details")), "client": R("clients", r.get("ticket_client_id")), "contact": R("contacts", r.get("ticket_contact_id")),
                    "contact_name": s(r.get("ticket_contact_name"), 150), "contact_email": email(r.get("ticket_contact_email")),
                    "assigned_to": R("users", r.get("ticket_assigned_to")), "priority": title(r.get("ticket_priority"), ["Critical", "High", "Medium", "Low"], "Medium"),
                    "status": TICKET_STATUS.get(str(r.get("ticket_status") or "").lower(), "Open"), "category": s(r.get("ticket_category"), 100),
                    "source": title(r.get("ticket_source"), ["Manual", "Email", "Portal", "Phone", "Alert", "Import"], "Import"),
                    "billable": True if r.get("ticket_billable") is None else yes(r.get("ticket_billable")), "due_date": day(r.get("ticket_due_date")),
                    "response_due_at": ts(r.get("ticket_sla_response_due")), "first_response_at": ts(r.get("ticket_first_response_at")),
                    "resolved_at": ts(r.get("ticket_resolved_at")), "closed_at": ts(r.get("ticket_closed_at")), "sla_breached": yes(r.get("ticket_sla_breached")),
                    "queue": R("queues", r.get("ticket_queue_id")), "cc": txt(r.get("ticket_cc")) or "", "resolution": txt(r.get("ticket_resolution")) or "",
                    "snoozed_until": ts(r.get("ticket_snoozed_until")),
                    "resolve_due_at": ts(r.get("ticket_sla_resolve_due") or r.get("ticket_sla_resolution_due")),
                    "created_at": ts(r.get("ticket_created_at")), "updated_at": ts(r.get("ticket_updated_at")) or ts(r.get("ticket_created_at"))}
        self.upsert("tickets", Ticket, rows, "ticket_id", ticket)
        for r in rows:  # merged tickets point at a ticket that may come later in the list
            target = R("tickets", r.get("ticket_merged_into"))
            if target:
                Ticket.objects.filter(legacy_id=int(r["ticket_id"])).exclude(pk=target).update(merged_into_id=target)

        # Messages: the original request is shown from the ticket itself; old replies become messages.
        user_names = {int(u["user_id"]): str(u.get("user_name") or "") for u in self.read("users", "user_id")}
        contact_names = {int(c["contact_id"]): str(c.get("contact_name") or "") for c in self.read("contacts", "contact_id")}
        replies = self.read("ticket_replies", "reply_id")
        ticket_contact = dict(Ticket.objects.filter(legacy_id__isnull=False).values_list("pk", "contact_name"))
        step = Step("ticket messages", source=len(replies))
        for r in replies:
            tid = R("tickets", r.get("reply_ticket_id"))
            if not tid:
                step.skipped += 1
                continue
            frm = str(r.get("reply_from") or "staff")
            # Old automatic messages (idle nudges, workflow changes, AI notes) are events, never shown to the client.
            kind = "event" if frm == "system" else {"note": "note", "work": "work"}.get(str(r.get("reply_type") or ""), "reply")
            name = user_names.get(int_(r.get("reply_user_id")) or 0) or contact_names.get(int_(r.get("reply_contact_id")) or 0) or ""
            if not name and frm == "client":
                name = ticket_contact.get(tid, "") or "Client"
            TicketMessage.objects.update_or_create(legacy_id=int(r["reply_id"]), defaults={
                "ticket_id": tid, "kind": kind, "body": txt(r.get("reply_body")) or "",
                "author_id": R("users", r.get("reply_user_id")),
                "author_name": name[:200],
                "via": "web" if frm == "staff" else frm[:20], "created_at": ts(r.get("reply_created_at")) or timezone.now(),
            })
            step.imported += 1
        self._done(step)

        def work_type(v):
            v = str(v or "")
            return "On-site" if re.search("site", v, re.I) else "Phone" if re.search("phone", v, re.I) else "Travel" if re.search("travel", v, re.I) else "Remote"
        entries = []
        for r in self.read("ticket_time_entries", "tte_id"):
            entries.append((int(r["tte_id"]), r.get("tte_ticket_id"), r.get("tte_user_id"), r.get("tte_hours"), work_type(r.get("tte_work_type")),
                            r.get("tte_description"), yes(r.get("tte_billable")), day(r.get("tte_date")), r.get("tte_invoice_id")))
        for r in replies:  # older tickets logged time on the reply itself
            if (num(r.get("reply_time_spent")) or 0) > 0:
                entries.append((10_000_000 + int(r["reply_id"]), r.get("reply_ticket_id"), r.get("reply_user_id"), r.get("reply_time_spent"), "Remote",
                                r.get("reply_work_type"), yes(r.get("reply_billable")), day(r.get("reply_created_at")), r.get("reply_invoice_id")))
        step = Step("ticket time", source=len(entries))
        for lid, t, u, hours, wt, desc, billable, wd, inv in entries:
            tid, minutes = R("tickets", t), round(float(num(hours) or 0) * 60)
            if not tid or minutes <= 0:
                step.skipped += 1
                continue
            TimeEntry.objects.update_or_create(legacy_id=lid, defaults={
                "ticket_id": tid, "user_id": R("users", u), "minutes": minutes, "work_type": wt, "description": txt(desc) or "",
                "billable": billable, "work_date": wd or dt.date(2000, 1, 1), "invoice_id": R("invoices", inv),
            })
            step.imported += 1
        self._done(step)

    def files(self):
        """Ticket attachments, client files and project files. The database only has the names;
        the files themselves come from the old app's uploads/ folder (--uploads). Safe to re-run:
        files already copied are left alone, so you can add the folder later."""
        import mimetypes
        import os

        from django.core.files import File

        from apps.files.models import Upload

        root = os.path.realpath(self.uploads_dir) if self.uploads_dir else None
        user_names = {int(u["user_id"]): str(u.get("user_name") or "") for u in self.read("users", "user_id")}
        sources = [
            ("ticket", "ticket_attachments", "attachment_id", "attachment_ticket_id", "tickets", "attachment_filename", "attachment_original_name",
             "attachment_mime_type", "attachment_uploaded_by", "attachment_created_at", None),
            ("client", "client_files", "file_id", "file_client_id", "clients", "file_filename", "file_original_name", "file_mime_type",
             "file_uploaded_by", "file_created_at", "file_notes"),
            ("project", "project_files", "file_id", "file_project_id", "projects", "file_filename", "file_original_name", "file_mime_type",
             "file_uploaded_by", "file_created_at", "file_notes"),
        ]
        reply_map = dict(TicketMessage.objects.filter(legacy_id__isnull=False).values_list("legacy_id", "pk"))
        for kind, table, key, owner_col, owner_kind, fn_col, name_col, mime_col, by_col, at_col, notes_col in sources:
            rows = self.read(table, key)
            step = Step(f"{kind} files", source=len(rows))
            waiting = 0
            for r in rows:
                lid = f"{kind}:{r[key]}"
                owner_old = int_(r.get(owner_col))
                owner = self.ref(owner_kind, owner_old)
                if not owner:
                    step.skipped += 1
                    continue
                if Upload.objects.filter(legacy_id=lid).exists():
                    step.kept += 1
                    continue
                if not root:
                    waiting += 1
                    continue
                stored = os.path.basename(str(r.get(fn_col) or ""))
                path = os.path.realpath(os.path.join(root, f"{kind}s", str(owner_old), stored))
                if not stored or not path.startswith(root + os.sep) or not os.path.isfile(path):
                    step.warnings.append(f"{kind} file {r[key]} ({r.get(name_col)}): not found in the uploads folder")
                    continue
                if self.dry_run:  # don't write files that the rollback would orphan
                    step.imported += 1
                    continue
                name = os.path.basename(str(r.get(name_col) or stored))[:255]
                u = Upload(kind=kind, original_name=name, size=os.path.getsize(path), legacy_id=lid,
                           content_type=(str(r.get(mime_col) or "") or mimetypes.guess_type(name)[0] or "application/octet-stream")[:100],
                           uploaded_by_id=self.ref("users", r.get(by_col)), uploaded_by_name=user_names.get(int_(r.get(by_col)) or 0, "")[:200],
                           notes=(s(r.get(notes_col)) or "") if notes_col else "", created_at=ts(r.get(at_col)) or timezone.now())
                setattr(u, f"{kind}_id", owner)
                if kind == "ticket" and r.get("attachment_reply_id"):
                    u.message_id = reply_map.get(int_(r["attachment_reply_id"]))
                with open(path, "rb") as fh:
                    u.file.save(name, File(fh), save=True)
                step.imported += 1
            if waiting:
                step.warnings.append(f"{waiting} {kind} file(s) not brought over yet: import again with the zipped uploads folder")
            self._done(step)

    def settings(self):
        """Every old setting: kept in LegacySetting, and copied into the new setting when there is one
        and it hasn't been set here yet. Old passwords/keys are decrypted with the old APP_KEY."""
        from apps.core.models import Setting
        from apps.core.settings_catalog import ALL_FIELDS

        from .crypto import decrypt_setting_value
        from .models import LegacySetting
        from .settings_map import DAY_KEYS, DAY_NAMES, MAP, SECRET_KEY_RX, SKIP_RX

        rows = self.read("settings", "setting_key") if self.has("settings") else []
        old = {str(r["setting_key"]): ("" if r.get("setting_value") is None else str(r["setting_value"])) for r in rows}
        step = Step("settings", source=len(old))
        bad_secrets = []

        def put(new_key, value, secret, legacy_row):
            if value is None or value.strip() in ("", "NULL") or (new_key in ALL_FIELDS and ALL_FIELDS[new_key]["type"] == "bool" and value not in ("true", "false")):
                return
            if new_key in ("email.imap_last_uid", "email.imap_uidvalidity") and not Setting.get("email.last_fetch", ""):
                # Until this app reads the mailbox itself, follow the old app's place in it (a newer backup = further along)
                cur = Setting.get(new_key, "")
                if new_key == "email.imap_uidvalidity" or not cur.isdigit() or (value.isdigit() and int(value) > int(cur)):
                    Setting.put(new_key, value)
                legacy_row.copied = True
                return
            if Setting.objects.filter(key=new_key).exclude(value="").exists():
                legacy_row.copied = Setting.get(new_key, "") == value[:20000]  # same as before (an earlier import) or changed here
                return  # changed here already — keep it
            Setting.put(new_key, value[:20000], secret=secret or ALL_FIELDS.get(new_key, {}).get("type") == "secret")
            legacy_row.copied = True

        for key, raw in sorted(old.items()):
            if SKIP_RX.match(key):
                step.skipped += 1
                continue
            secret = raw.startswith("enc1:") or bool(SECRET_KEY_RX.search(key))
            value, failed = raw, False
            if raw.startswith("enc1:"):
                try:
                    value = decrypt_setting_value(raw, self.app_key) if self.app_key else None
                except LegacyDecryptError:
                    value = None
                if value is None:
                    failed = True
                    bad_secrets.append(key)
            row = LegacySetting.objects.filter(key=key).first() or LegacySetting(key=key)
            row.is_secret, row.decrypt_failed = secret, failed
            if secret:
                row.value, row.secret_value = "", (value or "")
            else:
                row.value, row.secret_value = value or "", ""
            target = MAP.get(key)
            row.mapped_to = target[0] if target else ""
            row.copied = False
            if target and target[1] is None:
                row.copied = True  # handled below
            elif target and value is not None:
                put(target[0], target[1](value.strip() if not secret else value), secret, row)
            row.save()
            step.imported += 1
        # combined values
        addr = ", ".join(x for x in [old.get("company_address", ""), old.get("company_city", ""), " ".join(filter(None, [old.get("company_state", ""), old.get("company_zip", "")]))] if x and x != "NULL")
        if addr and not Setting.get("company.address", ""):
            Setting.put("company.address", addr)
        days = [DAY_NAMES[i] for i, k in enumerate(DAY_KEYS) if old.get(k) == "1"]
        if days and not Setting.get("helpdesk.days", ""):
            Setting.put("helpdesk.days", ",".join(days))
        # Google Workspace sign-in like the old app: allowed domains = the staff email domains,
        # and staff who had linked Google must keep using it (sso_require_for_linked).
        staff = self.read("users", "user_id") if self.has("users") else []
        if old.get("sso_google_enabled") == "1" and not Setting.get("google.domains", ""):
            doms = sorted({str(u.get("user_email") or "").rsplit("@", 1)[-1].lower() for u in staff if "@" in str(u.get("user_email") or "")})
            if doms:
                Setting.put("google.domains", ", ".join(doms))
        if old.get("sso_require_for_linked") == "1":
            for u in staff:
                if str(u.get("user_sso_provider") or "") == "google":
                    User.objects.filter(legacy_id=int(u["user_id"]), google_only=False, google_linked_at__isnull=True).update(
                        google_only=True, google_linked_at=ts(u.get("user_sso_linked_at")))
        if old.get("company_email") and not Setting.get("email.support_address", ""):
            Setting.put("email.support_address", old.get("imap_user") or old["company_email"])
        for k in ("company_address", "company_city", "company_state", "company_zip") + tuple(DAY_KEYS):
            LegacySetting.objects.filter(key=k).update(mapped_to={"helpdesk_day": "helpdesk.days"}.get(k[:12], "company.address"), copied=True)
        if bad_secrets:
            step.warnings.append(f"{len(bad_secrets)} saved password(s)/key(s) couldn't be unlocked ({', '.join(bad_secrets[:8])}"
                                 f"{'…' if len(bad_secrets) > 8 else ''}). Add the old config.php and import again, or type them in Settings.")
        self._done(step)

    def bump_counters(self):
        """Carry the old prefixes/padding over (unless already set here) and move each counter past
        the highest imported number that uses that prefix (other prefixes, e.g. old Zendesk ones, are ignored)."""
        from apps.core.models import Setting
        from apps.core.numbering import COUNTER, prefix

        old = {str(r["setting_key"]): str(r.get("setting_value") or "") for r in self.read("settings", "setting_key")}
        for kind in ("ticket", "invoice", "quote", "contract"):
            val = old.get(f"{kind}_prefix", "").strip()
            if val and not Setting.get(f"numbers.{kind}_prefix", ""):
                Setting.put(f"numbers.{kind}_prefix", val[:20])
        for kind, model in (("ticket", Ticket), ("invoice", Invoice), ("quote", Quote), ("contract", Contract), ("project", Project)):
            p = prefix(kind)
            # Padding: copy what the most recent old number actually looks like (e.g. ITDS-00917 → 5 digits).
            latest = model.objects.filter(number__startswith=p, legacy_id__isnull=False).order_by("-legacy_id").values_list("number", flat=True).first()
            digits = (latest or "")[len(p):]
            if digits.isdigit() and digits.startswith("0") and not Setting.get(f"numbers.{kind}_padding", ""):
                Setting.put(f"numbers.{kind}_padding", str(len(digits)))
            nums = [int(n[len(p):]) for n in model.objects.filter(number__startswith=p).values_list("number", flat=True) if n[len(p):].strip().isdigit()]
            if nums and max(nums):
                Counter.at_least(COUNTER[kind], max(nums))
