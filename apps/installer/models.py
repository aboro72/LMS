from django.db import models


class InstallationState(models.Model):
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Installationsstatus"
        verbose_name_plural = "Installationsstatus"

