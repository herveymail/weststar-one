from django.db import migrations, models

OLD_TERMS = "A late fee of $35.00 will be assessed on any balance not paid by the due date"
NEW_TERMS = "A late fee of {late_fee} will be assessed on any balance more than {grace_days} days past due"


def late_fee_45(apps, schema_editor):
    """Casey, Oct 2026: $45 late fee on any account more than 10 days past due."""
    Setting = apps.get_model("core", "Setting")

    def put(k, v):
        Setting.objects.update_or_create(key=k, defaults={"value": v, "is_secret": False})

    put("billing.late_fee_enabled", "true")
    put("billing.late_fee_type", "flat")
    put("billing.late_fee_flat", "45.00")
    put("billing.late_fee_grace_days", "10")
    for key, old, new in (("billing.invoice_terms", OLD_TERMS, NEW_TERMS), ("billing.late_notice", "A $35.00 late fee", "A {late_fee} late fee")):
        row = Setting.objects.filter(key=key, is_secret=False).first()
        if row and old in row.value:
            row.value = row.value.replace(old, new)
            row.save(update_fields=["value"])


class Migration(migrations.Migration):
    dependencies = [("billing", "0002_autopay"), ("core", "0001_initial")]

    operations = [
        migrations.AddField(model_name="invoice", name="last_late_fee_on",
                            field=models.DateField(blank=True, editable=False, null=True, verbose_name="Last late fee")),
        migrations.RunPython(late_fee_45, migrations.RunPython.noop),
    ]
