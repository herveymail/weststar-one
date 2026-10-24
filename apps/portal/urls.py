from django.urls import path

from . import views as v

urlpatterns = [
    path("", v.home, name="portal_home"),
    path("login/", v.login_view, name="portal_login"),
    path("login/code/", v.login_code, name="portal_login_code"),
    path("logout/", v.logout_view, name="portal_logout"),
    path("forgot/", v.forgot, name="portal_forgot"),
    path("link/<str:token>/", v.link_view, name="portal_link"),
    path("tickets/", v.tickets, name="portal_tickets"),
    path("tickets/<int:pk>/", v.ticket, name="portal_ticket"),
    path("files/<int:pk>/", v.file_download, name="portal_file"),
    path("invoices/", v.invoices, name="portal_invoices"),
    path("invoices/<int:pk>/", v.invoice, name="portal_invoice"),
    path("autopay/", v.autopay, name="portal_autopay"),
    path("autopay/link/<str:token>/", v.autopay_link, name="portal_autopay_link"),
    path("<slug:kind>/<int:pk>/pdf/", v.document_pdf, name="portal_pdf"),
    path("quotes/", v.quotes, name="portal_quotes"),
    path("quotes/<int:pk>/", v.quote, name="portal_quote"),
    path("contracts/", v.contracts, name="portal_contracts"),
    path("contracts/<int:pk>/", v.contract, name="portal_contract"),
    path("policies/", v.policies, name="portal_policies"),
    path("policies/<int:pk>/", v.policy, name="portal_policy"),
    path("assets/", v.assets, name="portal_assets"),
    path("help/", v.help_home, name="portal_help"),
    path("help/<int:pk>/", v.help_article, name="portal_article"),
    path("messages/", v.messages_list, name="portal_messages"),
    path("messages/<int:pk>/", v.message_thread, name="portal_message"),
    path("profile/", v.profile, name="portal_profile"),
]
