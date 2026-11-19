"""Ocean glass is the system look: new staff get it with the icon menu, and can still switch in Profile."""
import pytest

from apps.accounts.models import User
from apps.core.models import Setting

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


@pytest.fixture
def me(client):
    Setting.put("security.require_mfa", "nobody")
    u = make_user(role="admin", email="look@example.com")
    signed_in(client, u)
    return u


def test_new_staff_get_ocean_glass_with_the_icon_menu(client, me):
    assert (me.ui_style, me.menu_style) == ("ocean", "icons")
    html = client.get("/").content.decode()
    assert 'data-style="ocean"' in html and 'data-look="ocean"' in html and 'data-mode="dark"' in html
    assert "core/ocean.css" in html and 'class="rail"' in html


def test_picking_a_colour_theme_moves_to_classic_and_reset_comes_back(client, me):
    client.post("/profile/", {"look": "forest"})
    me.refresh_from_db()
    assert (me.look, me.ui_style) == ("forest", "classic")
    assert 'data-look="forest"' in client.get("/").content.decode()
    client.post("/profile/", {"reset_look": "1"})
    assert User.objects.get(pk=me.pk).ui_style == "ocean"
