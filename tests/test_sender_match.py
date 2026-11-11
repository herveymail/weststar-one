"""Email-to-ticket client matching by domain, and saving an unknown sender as a contact."""
import pytest

from apps.core.models import Setting
from apps.crm.models import Client, Contact
from apps.helpdesk.inbound import match_client
from apps.helpdesk.models import Ticket

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


def test_domain_matching():
    dd = Client.objects.create(name="Desert Dental", email_domains="desertdental.com, @dd-mail.com")
    Client.objects.create(name="Law Co", email="office@lawco.test")
    assert match_client("new.person@desertdental.com") == (dd, None)
    assert match_client("x@mail.desertdental.com")[0] == dd  # subdomains count
    assert match_client("y@dd-mail.com")[0] == dd
    assert match_client("a@lawco.test")[0].name == "Law Co"  # the client's own email domain
    assert match_client("someone@gmail.com") == (None, None)
    Client.objects.create(name="Other", email_domains="desertdental.com")
    assert match_client("z@desertdental.com") == (None, None)  # two clients claim it: a person decides
    c = Contact.objects.create(client=dd, name="Pat", email="pat@desertdental.com")
    assert match_client("PAT@desertdental.com") == (dd, c)


def test_add_unknown_sender_as_contact(client):
    Setting.put("security.require_mfa", "nobody")
    signed_in(client, make_user(role="admin"))
    dd = Client.objects.create(name="Desert Dental")
    t = Ticket.objects.create(number="T-9", subject="Help", contact_name="Sam Smith", contact_email="sam@desertdental.com", source="Email")
    page = client.get(f"/tickets/{t.pk}/?classic=1")
    assert b"isn&#x27;t a saved contact" in page.content or b"isn't a saved contact" in page.content
    assert b"@desertdental.com" in page.content
    client.post(f"/tickets/{t.pk}/contact/", {"client": dd.pk, "remember": "1"})
    t.refresh_from_db()
    dd.refresh_from_db()
    assert t.client == dd and t.contact.name == "Sam Smith" and t.contact.email == "sam@desertdental.com"
    assert dd.email_domains == "desertdental.com"
    assert match_client("someone.new@desertdental.com")[0] == dd
    assert b"saved contact" not in client.get(f"/tickets/{t.pk}/?classic=1").content
