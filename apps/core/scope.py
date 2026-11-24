"""Client scope: a staff login that may only work with certain clients (a contractor).

Settings › Users › a person › "Only these clients". While such a person's request is being handled, every query for
tickets, ticket messages, time, sign-offs, clients, contacts, devices, calendar events and files is narrowed to those
clients — in one place (the models' default manager), so no screen has to remember to do it. The middleware in
apps/accounts/middleware.py turns it on per request and keeps the person out of everything except the ticket screens.

Nothing is narrowed outside a request (background jobs, email-to-ticket, the shell).
"""
from contextvars import ContextVar

from django.db import models

_scope: ContextVar[frozenset | None] = ContextVar("client_scope", default=None)


def current() -> frozenset | None:
    """Client ids the current request is limited to, or None for no limit."""
    return _scope.get()


def enter(ids):
    return _scope.set(frozenset(ids))


def leave(token) -> None:
    _scope.reset(token)


class _Scoped(models.Manager):
    paths: tuple = ("client_id",)

    def get_queryset(self):
        qs = super().get_queryset()
        ids = current()
        if ids is None:
            return qs
        q = models.Q()
        for p in self.paths:
            q |= models.Q(**{f"{p}__in": ids})
        return qs.filter(q)


def ScopedManager(*paths):  # noqa: N802 — used like a class
    """Default manager for anything that belongs to a client. `paths` are the lookups that lead to the client id.

    The lookups live on the class, not the instance: Django builds its own copies of a manager for related sets
    (ticket.messages, client.tickets) without passing our arguments, and those copies must be narrowed too."""
    return type("ScopedManager_" + "_".join(paths or ("client_id",)), (_Scoped,), {"paths": tuple(paths) or ("client_id",)})()


# What a client-limited login may open. Everything else is refused.
ALLOWED = ("/tickets/", "/tech/", "/files/", "/profile/", "/account/", "/logout/", "/login/", "/static/", "/brand/", "/health/", "/legal/", "/clock/", "/settings/my_security/")
