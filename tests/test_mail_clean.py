"""Outgoing email is cleaned before it reaches the mail service, so one odd header or address can't stop a ticket reply."""
import json
import urllib.error
from io import BytesIO

import pytest

from apps.core import mail
from apps.core.models import OutboxEmail, Setting

pytestmark = pytest.mark.django_db
FOLDED = "\r\n <BYAPR07MB5637E3B1A2C4D5E6F7A8B9C0D1E2F3A4B5C6D7@BYAPR07MB5637.namprd07.prod.outlook.com>"


@pytest.fixture
def smtp2go(monkeypatch):
    Setting.put("email.provider", "SMTP2GO (HTTPS)")
    Setting.put("email.smtp2go_api_key", "api-test")
    Setting.put("email.from_address", "support@weststarmsp.com")
    Setting.put("email.from_name", "Weststar MSP, Inc.")
    sent = []

    class Ok:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"data": {"succeeded": 1}}'

    def fake(req, timeout=0):
        body = json.loads(req.data)
        sent.append(body)
        if fake.reject and any(h["header"] == "References" for h in body.get("custom_headers", [])):
            raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, BytesIO(json.dumps({"data": {
                "error": "An error occurred processing the json data you sent with the request.",
                "error_code": "E_ApiResponseCodes.NON_VALIDATING_IN_PAYLOAD",
                "field_validation_errors": {"fieldname": "custom_headers", "message": "Invalid header value"}}}).encode()))
        return Ok()
    fake.reject = False
    monkeypatch.setattr(mail.urllib.request, "urlopen", fake)
    return sent, fake


def test_addresses_and_message_ids_are_cleaned():
    assert mail.clean_address("  jbialek@rufenacht.net ,") == "jbialek@rufenacht.net"
    assert mail.clean_address("Jo  Bialek <jbialek@rufenacht.net>") == "Jo Bialek <jbialek@rufenacht.net>"
    assert mail.clean_address("not an address") == "" and mail.clean_address("a@b") == ""
    assert mail.clean_ids([FOLDED, "<no-id-7-abc@local>", "junk", "<a@b.c> <d@e.f>"]) == [FOLDED.strip(), "<a@b.c>", "<d@e.f>"]


def test_a_reply_to_a_folded_message_id_goes_out_clean(smtp2go):
    sent, _ = smtp2go
    assert mail.send(["jbialek@rufenacht.net ", "bad address"], "Re: Printer\n", "email/portal_staff_notice", {"what": "x", "detail": "y", "link": "https://x"},
                     cc=["boss@rufenacht.net;"], message_id="<ws1.t5.abc@weststarmsp.com>", references=[FOLDED, "<no-id-1-ff@local>"])
    b = sent[0]
    assert b["to"] == ["jbialek@rufenacht.net"] and b["cc"] == ["boss@rufenacht.net"] and b["subject"] == "Re: Printer"
    h = {x["header"]: x["value"] for x in b["custom_headers"]}
    assert h["In-Reply-To"] == FOLDED.strip() and h["References"] == FOLDED.strip() and h["Message-ID"] == "<ws1.t5.abc@weststarmsp.com>"
    assert not any("\n" in v or "\r" in v or v != v.strip() for v in h.values())
    assert b["sender"] == '"Weststar MSP, Inc." <support@weststarmsp.com>'


def test_if_the_service_refuses_the_headers_the_email_still_goes_and_real_reasons_are_kept(smtp2go):
    sent, fake = smtp2go
    fake.reject = True
    assert mail.send("jbialek@rufenacht.net", "Re: Printer", "email/portal_staff_notice", {"what": "x", "detail": "y", "link": "https://x"},
                     message_id="<ws1.t5.abc@weststarmsp.com>", references=["<a@b.c>"])
    assert len(sent) == 2 and all(h["header"] == "Reply-To" for h in sent[1].get("custom_headers", []))
    # nothing to drop: the reason SMTP2GO gives (which field) is what gets shown
    with pytest.raises(mail.Smtp2goRejected, match="custom_headers: Invalid header value"):
        mail._smtp2go_post({"sender": "a@b.c", "to": ["x@y.z"], "custom_headers": [{"header": "References", "value": "x"}]})


def test_try_failed_emails_again(smtp2go):
    sent, _ = smtp2go
    row = OutboxEmail.objects.create(status="failed", tries=5, to="jbialek@rufenacht.net", subject="Re: Printer", last_error="json data",
                                     payload={"body": "hi", "from": "support@weststarmsp.com", "headers": {"References": FOLDED}})
    assert mail.retry_failed() == 1
    assert mail.deliver_outbox() == {"sent": 1, "failed": 0}
    row.refresh_from_db()
    assert row.status == "sent" and sent[0]["custom_headers"][0]["value"] == FOLDED.strip()
