import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.accounts.models import Rolle


class LizenzTyp(models.TextChoices):
    BASIC = "basic", "Basic"
    PRO = "pro", "Pro"
    ENTERPRISE = "enterprise", "Enterprise"


def default_invitation_expiry():
    return timezone.now() + timedelta(days=7)


class Organisation(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to="logos/", blank=True)
    kontakt_email = models.EmailField()
    website = models.URLField(blank=True)
    lizenz_typ = models.CharField(max_length=20, choices=LizenzTyp.choices, default=LizenzTyp.BASIC)
    max_nutzer = models.PositiveIntegerField(default=50)
    max_kurse = models.PositiveIntegerField(default=10)
    aktiv = models.BooleanField(default=True)
    erstellt_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Organisation"
        verbose_name_plural = "Organisationen"

    def __str__(self):
        return self.name


class Einladung(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    email = models.EmailField()
    rolle = models.CharField(max_length=20, choices=Rolle.choices)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    eingeladen_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    erstellt_am = models.DateTimeField(auto_now_add=True)
    akzeptiert_am = models.DateTimeField(null=True, blank=True)
    abgelaufen_am = models.DateTimeField(default=default_invitation_expiry)

    class Meta:
        ordering = ["-erstellt_am"]
        verbose_name = "Einladung"
        verbose_name_plural = "Einladungen"

    def __str__(self):
        return f"{self.email} - {self.organisation} ({self.get_rolle_display()})"

    @property
    def ist_abgelaufen(self):
        return timezone.now() >= self.abgelaufen_am
