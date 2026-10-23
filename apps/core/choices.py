def C(*options):
    """choices=C('Active', 'Lead') → [('Active', 'Active'), ('Lead', 'Lead')]"""
    return [(o, o) for o in options]


def money(**kw):
    from django.db import models
    return models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, **kw)
