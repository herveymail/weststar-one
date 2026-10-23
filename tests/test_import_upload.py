"""Importing by uploading the old backup in Settings › Import (no database server, no commands)."""
import gzip
import io
import os
import zipfile
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.models import Setting
from apps.files.models import Upload
from apps.helpdesk.models import Ticket, TicketMessage
from apps.legacy.dumpreader import DumpSource
from apps.legacy.models import ImportRun
from apps.legacy.uploaded import _safe_extract, process_queued

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db

DUMP = r"""/*M!999999\- enable the sandbox mode */
-- MariaDB dump 10.19-11.8.3-MariaDB
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `user_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_name` varchar(100) DEFAULT NULL,
  `user_email` varchar(255) NOT NULL,
  `user_password` varchar(255) DEFAULT NULL,
  `user_role` varchar(20) DEFAULT 'tech',
  PRIMARY KEY (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci `ENCRYPTED`=YES;
INSERT INTO `users` VALUES (1,'Jose O\'Neil','jose@weststarmsp.com','$2y$10$abcdefghijklmnopqrstuuJ0j5Qm1Yy4nW8iC6zS4p2a6m8kq0w2e','tech');
CREATE TABLE `tickets` (
  `ticket_id` int(11) NOT NULL AUTO_INCREMENT,
  `ticket_number` varchar(30) DEFAULT NULL,
  `ticket_subject` varchar(255) DEFAULT NULL,
  `ticket_details` text DEFAULT NULL,
  `ticket_status` varchar(30) DEFAULT NULL,
  `ticket_priority` varchar(20) DEFAULT NULL,
  `ticket_assigned_to` int(11) DEFAULT NULL,
  `ticket_created_at` datetime DEFAULT NULL,
  `ticket_amount` decimal(10,2) DEFAULT NULL,
  PRIMARY KEY (`ticket_id`)
);
INSERT INTO `tickets` VALUES (7,'ITDS-00041','Printer \"jam\", again','Line one\nLine two; with ; semicolons\\ and a backslash','waiting_on_client','high',1,'2026-10-01 09:15:00',12.50),(8,'ITDS-00042','It''s fixed',NULL,'closed','low',NULL,'0000-00-00 00:00:00',-3);
CREATE TABLE `ticket_replies` (
  `reply_id` int(11) NOT NULL,
  `reply_ticket_id` int(11) NOT NULL,
  `reply_user_id` int(11) DEFAULT NULL,
  `reply_body` text,
  `reply_type` varchar(10) DEFAULT 'reply',
  `reply_created_at` datetime DEFAULT NULL
);
INSERT INTO `ticket_replies` VALUES (3,7,1,'On my way ☕','note','2026-10-01 10:00:00');
CREATE TABLE `ticket_attachments` (
  `attachment_id` int(11) NOT NULL,
  `attachment_ticket_id` int(11) NOT NULL,
  `attachment_reply_id` int(11) DEFAULT NULL,
  `attachment_filename` varchar(255) NOT NULL,
  `attachment_original_name` varchar(255) NOT NULL,
  `attachment_mime_type` varchar(100) DEFAULT NULL,
  `attachment_uploaded_by` int(11) DEFAULT NULL,
  `attachment_created_at` datetime DEFAULT NULL
);
INSERT INTO `ticket_attachments` VALUES (1,7,3,'att_1.png','printer photo.png','image/png',1,'2026-10-01 10:00:00');
"""


def _gz(text):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as g:
        g.write(text.encode())
    return buf.getvalue()


def _uploads_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("uploads/tickets/7/att_1.png", b"\x89PNG photo")
        z.writestr("../../evil.txt", b"nope")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.FILE_UPLOAD_TEMP_DIR = None
    Setting.put("security.require_mfa", "nobody")


def test_dump_reader_values(tmp_path):
    p = tmp_path / "d.sql.gz"
    p.write_bytes(_gz(DUMP))
    src = DumpSource(str(p))
    t = src.read("tickets", "ticket_id")
    assert t[0]["ticket_subject"] == 'Printer "jam", again'
    assert t[0]["ticket_details"] == "Line one\nLine two; with ; semicolons\\ and a backslash"
    assert t[0]["ticket_amount"] == Decimal("12.50") and t[1]["ticket_amount"] == -3
    assert t[1]["ticket_subject"] == "It's fixed" and t[1]["ticket_details"] is None
    assert src.read("users", "user_id")[0]["user_name"] == "Jose O'Neil"
    assert src.read("ticket_replies", "reply_id")[0]["reply_body"] == "On my way ☕"


def test_upload_practice_then_import(client):
    admin = make_user("boss@weststarmsp.com", role="admin")
    signed_in(client, admin)
    r = client.post("/settings/import/", {
        "dump": SimpleUploadedFile("db_2026-10-22.sql.gz", _gz(DUMP)),
        "uploads": SimpleUploadedFile("uploads.zip", _uploads_zip()),
        "config": SimpleUploadedFile("config.php", b"<?php define('APP_KEY','k1'); define('ENCRYPTION_KEY','aa');"),
        "mode": "practice",
    })
    assert r.status_code == 302
    practice = ImportRun.objects.get()
    assert practice.status == "queued" and practice.dry_run and practice.old_app_key.startswith("v1:")
    assert process_queued() == 1
    practice.refresh_from_db()
    assert practice.status == "done", practice.log
    assert not Ticket.objects.exists()            # practice saves nothing
    assert os.path.isdir(practice.work_dir)       # kept for "Import now"
    assert b"Practice run finished" in client.get(f"/settings/import/run/{practice.pk}/").content

    r = client.post(f"/settings/import/run/{practice.pk}/import/")
    real = ImportRun.objects.exclude(pk=practice.pk).get()
    assert process_queued() == 1
    real.refresh_from_db()
    assert real.status == "done", real.log
    t = Ticket.objects.get(number="ITDS-00041")
    assert t.status == "Waiting on client" and t.priority == "High" and t.assigned_to.email == "jose@weststarmsp.com"
    assert TicketMessage.objects.get(legacy_id=3).kind == "note"
    f = Upload.objects.get()
    assert f.original_name == "printer photo.png" and f.message_id
    assert real.work_dir == "" and real.old_app_key == ""  # uploaded backup and keys are gone
    assert not os.path.exists(os.path.join(os.path.dirname(f.file.path), "..", "..", "..", "evil.txt"))


def test_only_admins_can_import(client):
    signed_in(client, make_user("mgr@weststarmsp.com", role="manager"))
    page = client.get("/settings/import/")
    assert page.status_code == 200 and b'name="dump"' not in page.content  # managers can look, not upload
    assert client.post("/settings/import/", {"dump": SimpleUploadedFile("x.sql", b"x")}).status_code == 403
    assert not ImportRun.objects.exists()


def test_bad_backup_fails_cleanly(client):
    signed_in(client, make_user("boss@weststarmsp.com", role="admin"))
    client.post("/settings/import/", {"dump": SimpleUploadedFile("notes.sql", b"hello there"), "mode": "import"})
    process_queued()
    run = ImportRun.objects.get()
    assert run.status == "failed" and "doesn't look like a database backup" in run.error
    assert run.work_dir == ""


def test_safe_extract_blocks_escapes(tmp_path):
    z = tmp_path / "u.zip"
    z.write_bytes(_uploads_zip())
    _safe_extract(str(z), str(tmp_path / "out"))
    assert (tmp_path / "out/uploads/tickets/7/att_1.png").exists()
    assert not (tmp_path / "evil.txt").exists() and not (tmp_path.parent / "evil.txt").exists()
