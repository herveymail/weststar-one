"""The classic ticket page cleared a ticket's queue whenever status, priority, assignee or category was changed there
(Oct 2026 bug). Put the queue back: the last queue the ticket was moved to, else the queue its routing words pick."""
import re

from django.db import migrations


def restore(apps, schema_editor):
    Ticket = apps.get_model("helpdesk", "Ticket")
    Queue = apps.get_model("helpdesk", "Queue")
    Msg = apps.get_model("helpdesk", "TicketMessage")
    queues = {q.name: q for q in Queue.objects.all()}
    lost = Msg.objects.filter(kind="event", body__startswith="Removed from queue by").values_list("ticket_id", flat=True).distinct()
    for t in Ticket.objects.filter(pk__in=list(lost), queue__isnull=True):
        before = Msg.objects.filter(ticket=t, kind="event", body__startswith="Moved to ").order_by("-created_at").first()
        q = None
        if before:
            m = re.match(r"Moved to (.+?) by ", before.body)
            q = queues.get(m.group(1)) if m else None
        if q is None:
            text = f"{t.subject} {t.details}".lower()
            for cand in Queue.objects.filter(active=True).order_by("sort", "id"):
                words = [w.strip().lower() for w in re.split(r"[,\n]", cand.keywords or "") if w.strip()]
                if any(w in text for w in words):
                    q = cand
                    break
        if q is None:
            q = Queue.objects.filter(active=True, is_default=True).first()
        if q is not None:
            Ticket.objects.filter(pk=t.pk).update(queue=q)
            Msg.objects.create(ticket=t, kind="event", body=f"Queue put back to {q.name} (it had been cleared by mistake)", via="system")


class Migration(migrations.Migration):
    dependencies = [("helpdesk", "0006_alter_ticket_source")]
    operations = [migrations.RunPython(restore, migrations.RunPython.noop)]
