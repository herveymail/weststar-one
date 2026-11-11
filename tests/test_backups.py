"""Settings › Backups: back up now, list, download, restore (with a safety backup first), nightly, off-site copy."""
import shutil
import tarfile
from datetime import datetime

import pytest
from django.conf import settings
from django.utils import timezone

from apps.core import backups
from apps.core.models import BackupRun, Setting
from apps.crm.models import Client

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db(transaction=True)
needs_pg = pytest.mark.skipif(not shutil.which("pg_dump"), reason="pg_dump not installed")


@pytest.fixture(autouse=True)
def folders(tmp_path, settings):
    settings.BACKUP_ROOT = tmp_path / "backups"
    settings.MEDIA_ROOT = tmp_path / "media"
    (tmp_path / "media" / "uploads").mkdir(parents=True)
    (tmp_path / "media" / "uploads" / "a.txt").write_text("hello")
    (tmp_path / "media" / ".upload-tmp").mkdir()
    Setting.put("backup.nightly", "false")
    return tmp_path


@pytest.fixture
def admin(client):
    Setting.put("security.require_mfa", "nobody")
    u = make_user(role="admin")
    signed_in(client, u)
    return u


@needs_pg
def test_backup_now_and_restore(client, admin, folders):
    Client.objects.create(name="Before")
    assert client.get("/settings/backups/").status_code == 200
    client.post("/settings/backups/", {"action": "backup"})
    assert BackupRun.objects.get().status == "queued"
    backups.run_queued()
    run = BackupRun.objects.filter(trigger="manual").get()
    assert run.status == "done", run.message
    b = backups.find(run.name)
    assert b and b["db_bytes"] > 0 and b["files"]
    with tarfile.open(backups.root() / b["files"]) as t:
        names = t.getnames()
    assert "media/uploads/a.txt" in names and not any(".upload-tmp" in n for n in names)
    dl = client.get(f"/settings/backups/download/{run.name}/db/")
    assert dl.status_code == 200 and b"".join(dl.streaming_content)[:5] == b"PGDMP"

    # change things, then restore
    Client.objects.create(name="After")
    (folders / "media" / "uploads" / "a.txt").write_text("changed")
    r = client.post("/settings/backups/", {"action": "restore", "name": run.name, "confirm": "restore"})
    assert not BackupRun.objects.filter(kind="restore").exists()  # wrong confirmation
    client.post("/settings/backups/", {"action": "restore", "name": run.name, "confirm": "RESTORE"})
    backups.run_queued()
    assert set(Client.objects.values_list("name", flat=True)) == {"Before"}
    assert (folders / "media" / "uploads" / "a.txt").read_text() == "hello"
    rec = BackupRun.objects.filter(kind="restore").get()
    assert rec.status == "done" and "Safety backup" in rec.message
    assert len(backups.listing()) == 2  # the original + the safety backup
    assert r.status_code == 302


def test_only_admins(client):
    Setting.put("security.require_mfa", "nobody")
    signed_in(client, make_user(role="tech"))
    assert client.get("/settings/backups/").status_code == 403


def test_nightly_once_a_day(settings):
    Setting.put("backup.nightly", "true")
    settings.TIME_ZONE = "America/Denver"
    early = timezone.make_aware(datetime(2026, 11, 10, 1, 0))
    later = early.replace(hour=3)
    assert backups.nightly(early) is False
    assert backups.nightly(later) is True
    assert backups.nightly(later.replace(hour=5)) is False
    Setting.put("backup.nightly", "false")
    BackupRun.objects.all().delete()
    assert backups.nightly(later) is False


def test_offsite_upload_signed(monkeypatch, folders):
    Setting.put("backup.s3_endpoint", "s3.us-west-1.wasabisys.com")
    Setting.put("backup.s3_bucket", "ws-backups")
    Setting.put("backup.s3_key", "AKIDEXAMPLE")
    Setting.put("backup.s3_secret", "secret", secret=True)
    seen = {}

    class Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(req, timeout=0):
        seen["url"], seen["auth"], seen["len"] = req.full_url, req.headers.get("Authorization"), req.headers.get("Content-length")
        return Resp()
    monkeypatch.setattr(backups.urllib.request, "urlopen", fake)
    f = folders / "x.dump"
    f.write_bytes(b"12345")
    assert backups.offsite_copy([f]) == "copied"
    assert seen["url"] == "https://s3.us-west-1.wasabisys.com/ws-backups/weststar-one/x.dump"
    assert seen["auth"].startswith("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/") and seen["len"] == "5"


def test_offsite_error_does_not_fail_backup(monkeypatch, folders):
    Setting.put("backup.s3_endpoint", "s3.example.test")
    Setting.put("backup.s3_bucket", "b")
    Setting.put("backup.s3_key", "k")
    Setting.put("backup.s3_secret", "s", secret=True)

    def boom(*a, **k):
        raise OSError("no route")
    monkeypatch.setattr(backups.urllib.request, "urlopen", boom)
    f = folders / "x.dump"
    f.write_bytes(b"1")
    assert backups.offsite_copy([f]).startswith("Off-site copy failed (no route)")


def test_safe_extract_blocks_escape(folders):
    bad = folders / "bad.tar.gz"
    with tarfile.open(bad, "w:gz") as t:
        p = folders / "evil.txt"
        p.write_text("x")
        t.add(str(p), arcname="../evil.txt")
    with tarfile.open(bad) as t, pytest.raises(RuntimeError):
        backups._safe_extract(t, folders / "out")
    assert settings.MEDIA_ROOT

