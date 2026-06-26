import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class Zahlungsart(models.TextChoices):
    STRIPE = "stripe", "Stripe"
    GOOGLE_PAY = "google_pay", "Google Pay"
    BANK_TRANSFER = "bank_transfer", "Ueberweisung"
    PAYPAL = "paypal", "PayPal"


class Zahlungsstatus(models.TextChoices):
    OFFEN = "offen", "Offen"
    BEZAHLT = "bezahlt", "Bezahlt"
    FEHLGESCHLAGEN = "fehlgeschlagen", "Fehlgeschlagen"
    STORNIERT = "storniert", "Storniert"


class Auszahlungsstatus(models.TextChoices):
    OFFEN = "offen", "Offen"
    GEMELDET = "gemeldet", "Betreiber informiert"
    AUSGEZAHLT = "ausgezahlt", "Ausgezahlt"


class Zahlungseinstellungen(models.Model):
    stripe_aktiv = models.BooleanField(default=False)
    stripe_public_key = models.CharField(max_length=255, blank=True)
    stripe_secret_key = models.CharField(max_length=255, blank=True)
    google_pay_aktiv = models.BooleanField(default=False)
    paypal_aktiv = models.BooleanField(default=False)
    paypal_client_id = models.CharField(max_length=255, blank=True)
    paypal_secret = models.CharField(max_length=255, blank=True)
    ueberweisung_aktiv = models.BooleanField(default=True)
    kontoinhaber = models.CharField(max_length=200, blank=True)
    iban = models.CharField(max_length=34, blank=True)
    bic = models.CharField(max_length=20, blank=True)
    bankname = models.CharField(max_length=200, blank=True)
    demo_autoconfirm = models.BooleanField(default=True)
    aktualisiert_am = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Zahlungseinstellungen"
        verbose_name_plural = "Zahlungseinstellungen"

    def __str__(self):
        return "Zahlungseinstellungen"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def aktive_zahlungsarten(self):
        choices = []
        if self.stripe_aktiv:
            choices.append((Zahlungsart.STRIPE, Zahlungsart.STRIPE.label))
            choices.append((Zahlungsart.GOOGLE_PAY, Zahlungsart.GOOGLE_PAY.label))
        elif self.google_pay_aktiv:
            choices.append((Zahlungsart.GOOGLE_PAY, Zahlungsart.GOOGLE_PAY.label))
        if self.paypal_aktiv:
            choices.append((Zahlungsart.PAYPAL, Zahlungsart.PAYPAL.label))
        if self.ueberweisung_aktiv:
            choices.append((Zahlungsart.BANK_TRANSFER, Zahlungsart.BANK_TRANSFER.label))
        return choices


class Zahlung(models.Model):
    zahlung_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="zahlungen")
    kurs = models.ForeignKey("courses.Kurs", on_delete=models.CASCADE, related_name="zahlungen")
    trainer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="trainer_zahlungen")
    zahlungsart = models.CharField(max_length=30, choices=Zahlungsart.choices)
    status = models.CharField(max_length=30, choices=Zahlungsstatus.choices, default=Zahlungsstatus.OFFEN)
    auszahlungsstatus = models.CharField(max_length=30, choices=Auszahlungsstatus.choices, default=Auszahlungsstatus.OFFEN)
    betrag_brutto = models.DecimalField(max_digits=10, decimal_places=2)
    plattform_gebuehr = models.DecimalField(max_digits=10, decimal_places=2)
    trainer_anteil = models.DecimalField(max_digits=10, decimal_places=2)
    waehrung = models.CharField(max_length=3, default="EUR")
    provider_referenz = models.CharField(max_length=255, blank=True)
    betreiber_notiz = models.TextField(blank=True)
    erstellt_am = models.DateTimeField(auto_now_add=True)
    bezahlt_am = models.DateTimeField(null=True, blank=True)
    ausgezahlt_am = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-erstellt_am"]
        verbose_name = "Zahlung"
        verbose_name_plural = "Zahlungen"

    def __str__(self):
        return f"{self.kurs} - {self.nutzer} - {self.betrag_brutto} {self.waehrung}"

    @classmethod
    def berechne_aufteilung(cls, betrag):
        brutto = Decimal(betrag)
        gebuehr = (brutto * Decimal(settings.PLATFORM_COMMISSION_PERCENT) / Decimal("100")).quantize(Decimal("0.01"))
        trainer_anteil = brutto - gebuehr
        return gebuehr, trainer_anteil
