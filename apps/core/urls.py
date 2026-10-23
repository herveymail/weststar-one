from django.urls import path

from apps.accounts import views as acc
from apps.crm import views as crm
from apps.helpdesk import views as hd
from apps.files import views as fv
from apps.hr import views as hr

from . import settings_views as sv
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("health/", views.health),
    path("login/", acc.login_view, name="login"),
    path("login/mfa/", acc.mfa_view, name="mfa"),
    path("login/google/", acc.google_start, name="google_start"),
    path("login/google/callback/", acc.google_callback, name="google_callback"),
    path("logout/", acc.logout_view, name="logout"),
    path("account/password/", acc.password_view, name="password"),
    path("account/mfa-setup/", acc.mfa_setup_view, name="mfa_setup"),
    path("profile/", acc.profile_view, name="profile"),
    path("search/", views.jump, name="jump"),
    path("tickets/", hd.tickets, name="tickets"),
    path("tickets/new/", hd.ticket_new, name="ticket_new"),
    path("tickets/<int:pk>/", hd.tickets, name="ticket"),
    path("tickets/<int:pk>/pane/", hd.ticket_pane, name="ticket_pane"),
    path("tickets/<int:pk>/update/", hd.ticket_update, name="ticket_update"),
    path("tickets/<int:pk>/message/", hd.ticket_message, name="ticket_message"),
    path("tickets/<int:pk>/time/", hd.ticket_time, name="ticket_time"),
    path("clients/", crm.clients, name="clients"),
    path("clients/<int:pk>/", crm.client_detail, name="client"),
    path("my-hr/", hr.my_hr, name="my_hr"),
    path("clock/", hr.clock, name="clock"),
    path("files/<int:pk>/", fv.download, name="file_download"),
    path("files/<int:pk>/delete/", fv.delete, name="file_delete"),
    path("files/<str:kind>/<int:pk>/", fv.file_list, name="file_list"),
    path("hr/", hr.hr_admin, name="hr"),
    path("settings/", sv.settings_home, name="settings"),
    path("settings/users/new/", acc.user_edit_view, name="user_new"),
    path("settings/users/<int:pk>/", acc.user_edit_view, name="user_edit"),
    path("settings/<slug:page>/", sv.settings_page, name="settings_page"),
    path("m/<slug:slug>/", views.module_list, name="module"),
    path("m/<slug:slug>/new/", views.module_edit, name="module_new"),
    path("m/<slug:slug>/<int:pk>/", views.module_edit, name="module_edit"),
    path("m/<slug:slug>/<int:pk>/archive/", views.module_archive, name="module_archive"),
    path("m/<slug:slug>/<int:pk>/reveal/<slug:field>/", views.module_reveal, name="module_reveal"),
]
