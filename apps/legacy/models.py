from django.db import models


class ImportRun(models.Model):
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    dry_run = models.BooleanField(default=False)
    summary = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True)

    @property
    def total(self):
        return sum(s.get("imported", 0) for s in (self.summary or []))

    @property
    def warnings(self):
        return sum(len(s.get("warnings", [])) for s in (self.summary or []))
