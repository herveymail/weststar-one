"""Imports a real copy of the OLD schema (MariaDB database `legacy`, filled by tests/fixtures/legacy-seed.php
with the old app's own encryption). Skipped when that database or PHP isn't available."""
import os
import shutil
import subprocess

import pytest

from apps.accounts.models import User
from apps.core.crypto import decrypt
from apps.core.models import Counter
from apps.crm.models import Client, Network
from apps.files.models import Upload
from apps.helpdesk.models import Ticket, TicketMessage
from apps.hr.models import Employee
from apps.legacy.importer import Importer
from apps.legacy.models import ImportRun

pytestmark = pytest.mark.django_db
APP_KEY = "old-app-key-from-config-php-0123456789abcdef"
ENC_KEY = "5f" * 32
LEGACY = dict(host=os.environ.get("LEGACY_DB_HOST", "127.0.0.1"), user=os.environ.get("LEGACY_DB_USER", "legacy"),
              password=os.environ.get("LEGACY_DB_PASSWORD", "legacy"), database=os.environ.get("LEGACY_DB_NAME", "legacy"))


@pytest.fixture(scope="module")
def legacy_conn():
    MySQLdb = pytest.importorskip("MySQLdb")
    if not shutil.which("php"):
        pytest.skip("php not installed (needed to build the old-format fixture)")
    try:
        conn = MySQLdb.connect(charset="utf8mb4", **LEGACY)
    except MySQLdb.Error:
        pytest.skip("legacy test database not available")
    env = {**os.environ, "OLD_APP_KEY": APP_KEY, "OLD_ENCRYPTION_KEY": ENC_KEY, "LEGACY_DB": LEGACY["database"],
           "LEGACY_DB_HOST": LEGACY["host"], "LEGACY_DB_USER": LEGACY["user"], "LEGACY_DB_PASSWORD": LEGACY["password"]}
    subprocess.run(["php", os.path.join(os.path.dirname(__file__), "fixtures", "legacy-seed.php")], env=env, check=True, capture_output=True)
    yield conn
    conn.close()


def test_dry_run_saves_nothing(legacy_conn):
    Importer(legacy_conn, APP_KEY, ENC_KEY, log=lambda *_: None).run(dry_run=True)
    assert not Ticket.objects.exists() and ImportRun.objects.get().dry_run


def test_full_import_is_repeatable_and_decrypts(legacy_conn):
    Importer(legacy_conn, APP_KEY, ENC_KEY, log=lambda *_: None).run()
    counts = (Ticket.objects.count(), TicketMessage.objects.count(), Client.objects.count(), User.objects.count())
    Importer(legacy_conn, APP_KEY, ENC_KEY, log=lambda *_: None).run()
    assert (Ticket.objects.count(), TicketMessage.objects.count(), Client.objects.count(), User.objects.count()) == counts
    assert Ticket.objects.filter(number="T-10482", status="Waiting on client").exists()
    casey = User.objects.get(email="casey@weststarmsp.com")
    assert casey.mfa_enabled and decrypt(casey.totp_secret_enc) == "JBSWY3DPEHPK3PXP"
    assert casey.check_password("Old-Password-123!")
    assert not User.objects.get(email="old@weststarmsp.com").is_active
    net = Network.objects.get(name="franklin.local")
    assert decrypt(net.wifi_password) == "Wifi-Pass-2026!" and decrypt(net.isp_account) == "ACCT-778899"
    assert Network.objects.filter(name="drd.local").exists()
    emp = Employee.objects.get()
    assert decrypt(emp.ssn).count("-") == 2
    assert Counter.objects.get(name="ticket").value >= 10482


def test_records_changed_here_are_not_overwritten(legacy_conn):
    """H3: edits made in the new app survive a re-import; staff keep their role."""
    Importer(legacy_conn, APP_KEY, ENC_KEY, log=lambda *_: None).run()
    t = Ticket.objects.get(number="T-10482")
    t.subject = "Edited in the new app"
    t.save()
    u = User.objects.get(email="tech1@weststarmsp.com")
    User.objects.filter(pk=u.pk).update(role="viewer")
    Importer(legacy_conn, APP_KEY, ENC_KEY, log=lambda *_: None).run()
    assert Ticket.objects.get(pk=t.pk).subject == "Edited in the new app"
    assert User.objects.get(pk=u.pk).role == "viewer"


def test_files_come_from_the_uploads_folder(legacy_conn, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / "media"
    with legacy_conn.cursor() as c:
        c.execute("SELECT ticket_id FROM tickets ORDER BY ticket_id LIMIT 1")
        tid = c.fetchone()[0]
        c.execute("DELETE FROM ticket_attachments")
        c.execute("INSERT INTO ticket_attachments (attachment_ticket_id, attachment_filename, attachment_original_name, attachment_mime_type, attachment_size) "
                  "VALUES (%s, 'att_abc.pdf', 'Quote from vendor.pdf', 'application/pdf', 4), (%s, '../../etc/passwd', 'x.txt', 'text/plain', 1)", (tid, tid))
    legacy_conn.commit()
    up = tmp_path / "uploads" / "tickets" / str(tid)
    up.mkdir(parents=True)
    (up / "att_abc.pdf").write_bytes(b"%PDF")
    imp = Importer(legacy_conn, APP_KEY, ENC_KEY, log=lambda *_: None, uploads_dir=str(tmp_path / "uploads"))
    imp.run()
    f = Upload.objects.get()
    assert f.original_name == "Quote from vendor.pdf" and f.file.read() == b"%PDF"
    step = next(s for s in imp.steps if s.name == "ticket files")
    assert step.imported == 1 and any("not found" in w for w in step.warnings)  # the ../ path was refused
    Importer(legacy_conn, APP_KEY, ENC_KEY, log=lambda *_: None, uploads_dir=str(tmp_path / "uploads")).run()
    assert Upload.objects.count() == 1
