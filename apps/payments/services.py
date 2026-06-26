from django.db import transaction
from django.utils import timezone

from apps.courses.models import Einschreibung

from .models import Zahlung, Zahlungsart, Zahlungseinstellungen, Zahlungsstatus


@transaction.atomic
def erstelle_zahlung(kurs, nutzer, zahlungsart):
    gebuehr, trainer_anteil = Zahlung.berechne_aufteilung(kurs.preis)
    return Zahlung.objects.create(
        nutzer=nutzer,
        kurs=kurs,
        trainer=kurs.erstellt_von,
        zahlungsart=zahlungsart,
        betrag_brutto=kurs.preis,
        plattform_gebuehr=gebuehr,
        trainer_anteil=trainer_anteil,
    )


@transaction.atomic
def bestaetige_zahlung(zahlung, provider_referenz=""):
    if zahlung.status == Zahlungsstatus.BEZAHLT:
        return zahlung
    zahlung.status = Zahlungsstatus.BEZAHLT
    zahlung.provider_referenz = provider_referenz or zahlung.provider_referenz
    zahlung.bezahlt_am = timezone.now()
    zahlung.save(update_fields=["status", "provider_referenz", "bezahlt_am"])
    Einschreibung.objects.update_or_create(
        nutzer=zahlung.nutzer,
        kurs=zahlung.kurs,
        defaults={"bezahlt": True},
    )
    return zahlung


def zahlungsart_ist_automatisch(zahlungsart):
    return zahlungsart in [Zahlungsart.STRIPE, Zahlungsart.GOOGLE_PAY, Zahlungsart.PAYPAL]


def lade_zahlungseinstellungen():
    return Zahlungseinstellungen.load()
