from django.shortcuts import redirect
from django.urls import path

from apps.accounts import views as acc
from apps.crm import views as crm
from apps.helpdesk import views as hd
from apps.files import views as fv
from apps.hr import views as hr
from apps.legacy import views as lv
from apps.portal import staff_views as psv
from apps.billing import pay_views, sign_views
from apps.helpdesk import tech_views as tech
from apps.billing import ready_views, ar_views

from apps.accounts.agreements import agreements as agreements_view

from . import legal_views
from apps.billing import views as bv
from apps.integrations import views as iv

from . import branding
from . import settings_views as sv
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("health/", views.health),
    path("brand/logo/", branding.logo_view, name="brand_logo"),
    path("login/", acc.login_view, name="login"),
    path("login/mfa/", acc.mfa_view, name="mfa"),
    path("login/google/", acc.google_start, name="google_start"),
    path("login/google/callback/", acc.google_callback, name="google_callback"),
    path("logout/", acc.logout_view, name="logout"),
    path("account/password/", acc.password_view, name="password"),
    path("account/mfa-setup/", acc.mfa_setup_view, name="mfa_setup"),
    path("account/agreements/", agreements_view, name="agreements"),
    path("profile/", acc.profile_view, name="profile"),
    path("search/", views.jump, name="jump"),
    path("tech/", tech.today, name="tech"),
    path("tech/tickets/", tech.tickets, name="tech_tickets"),
    path("tech/t/<int:pk>/", tech.ticket, name="tech_ticket"),
    path("tech/schedule/", tech.schedule, name="tech_schedule"),
    path("tech/time/", tech.time_tab, name="tech_time"),
    path("tech/me/", tech.me, name="tech_me"),
    path("tech/manifest.webmanifest", tech.manifest, name="tech_manifest"),
    path("tech/sw.js", tech.service_worker, name="tech_sw"),
    path("tech/offline/", tech.offline, name="tech_offline"),
    path("tickets/", hd.tickets, name="tickets"),
    path("tickets/new/", hd.ticket_new, name="ticket_new"),
    path("tickets/ui/", hd.switch_ui, name="tickets_ui"),
    path("tickets/bulk/", hd.bulk, name="tickets_bulk"),
    path("tickets/<int:pk>/", hd.ticket_detail, name="ticket"),
    path("tickets/<int:pk>/panel/", hd.ticket_panel, name="ticket_panel"),
    path("tickets/<int:pk>/update/", hd.ticket_update, name="ticket_update"),
    path("tickets/<int:pk>/message/", hd.ticket_message, name="ticket_message"),
    path("tickets/<int:pk>/timer/", hd.ticket_timer, name="ticket_timer"),
    path("tickets/<int:pk>/contact/", hd.ticket_contact, name="ticket_contact"),
    path("tickets/<int:pk>/snooze/", hd.ticket_snooze, name="ticket_snooze"),
    path("tickets/<int:pk>/merge/", hd.ticket_merge, name="ticket_merge"),
    path("tickets/<int:pk>/resolve/", hd.ticket_resolve, name="ticket_resolve"),
    path("tickets/<int:pk>/ai/", hd.ticket_ai, name="ticket_ai"),
    path("tickets/<int:pk>/signoff/", hd.ticket_signoff, name="ticket_signoff"),
    path("tickets/<int:pk>/approval/", hd.ticket_approval, name="ticket_approval"),
    path("tickets/<int:pk>/delete/", hd.ticket_delete, name="ticket_delete"),
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
    path("settings/import/run/<int:pk>/", lv.import_status, name="import_status"),
    path("settings/import/run/<int:pk>/import/", lv.import_again, name="import_again"),
    path("settings/import/run/<int:pk>/discard/", lv.import_discard, name="import_discard"),
    path("settings/email/test/", sv.email_test, name="email_test"),
    path("settings/payments/stripe/", sv.stripe_tools, name="stripe_tools"),
    path("settings/email/google/", sv.gmail_connect, name="gmail_connect"),
    path("settings/email/preview/<slug:name>/", sv.email_preview, name="email_preview"),
    path("settings/email/google/callback/", sv.gmail_connect, name="gmail_callback"),
    path("settings/<slug:page>/", sv.settings_page, name="settings_page"),
    path("m/messages/", psv.messages_list, name="messages"),
    path("messages/<int:pk>/", psv.message_thread, name="message"),
    path("clients/<int:pk>/portal/", psv.client_portal, name="client_portal"),
    path("clients/<int:pk>/autopay/", bv.client_autopay, name="client_autopay"),
    path("stripe/webhook/", bv.stripe_webhook, name="stripe_webhook"),
    path("pay/<str:token>/", pay_views.pay_page, name="pay_page"),
    path("legal/<slug:slug>/", legal_views.page, name="legal_page"),
    path("pay/<str:token>/pdf/", pay_views.pay_pdf, name="pay_pdf"),
    path("quote/<str:token>/", sign_views.quote_page, name="quote_public"),
    path("quote/<str:token>/pdf/", sign_views.quote_pdf, name="quote_public_pdf"),
    path("sign/<str:token>/", sign_views.contract_page, name="contract_public"),
    path("billing/ready/", ready_views.ready_page, name="ready_to_bill"),
    path("billing/ar/", ar_views.ar_page, name="receivables"),
    path("billing/ar/statement/<int:client_id>/", ar_views.statement, name="statement"),
    path("billing/contract/<int:pk>/send/", bv.contract_send, name="contract_send"),
    path("billing/renewal/<int:pk>/quote/", bv.renewal_quote, name="renewal_quote"),
    path("billing/<slug:kind>/<int:pk>/", bv.document, name="document"),
    path("billing/<slug:kind>/<int:pk>/pdf/", bv.document_pdf, name="document_pdf"),
    path("billing/<slug:kind>/<int:pk>/send/", bv.document_send, name="document_send"),
    path("backups/", iv.backups, name="backups"),
    path("backups/sync/", iv.backups_sync, name="backups_sync"),
    path("backups/test/", iv.backups_test, name="backups_test"),
    path("backups/companies/", iv.backups_companies, name="backups_companies"),
    path("m/backups/", lambda r: redirect("/backups/")),
    path("m/<slug:slug>/", views.module_list, name="module"),
    path("m/<slug:slug>/new/", views.module_edit, name="module_new"),
    path("m/<slug:slug>/<int:pk>/", views.module_edit, name="module_edit"),
    path("m/<slug:slug>/<int:pk>/archive/", views.module_archive, name="module_archive"),
    path("m/<slug:slug>/<int:pk>/reveal/<slug:field>/", views.module_reveal, name="module_reveal"),
]
