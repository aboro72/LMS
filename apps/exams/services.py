import random
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Antwort, Frage, Pruefung, PruefungsVersuch, TeilnehmerAntwort


class MaxVersucheErreicht(Exception):
    pass


@transaction.atomic
def starte_pruefung(pruefung, nutzer):
    bisherige_versuche = PruefungsVersuch.objects.filter(pruefung=pruefung, nutzer=nutzer).count()
    if pruefung.max_versuche is not None and bisherige_versuche >= pruefung.max_versuche:
        raise MaxVersucheErreicht("Maximale Anzahl an Versuchen erreicht.")

    fragen = list(Frage.objects.filter(fragenkatalog=pruefung.fragenkatalog, eltern_szenario__isnull=True))
    if pruefung.zufaellige_fragenreihenfolge:
        random.shuffle(fragen)
    fragen = fragen[: pruefung.anzahl_fragen]

    return PruefungsVersuch.objects.create(
        nutzer=nutzer,
        pruefung=pruefung,
        versuch_nummer=bisherige_versuche + 1,
        fragen_reihenfolge=[frage.id for frage in fragen],
    )


def speichere_antwort(versuch, frage, daten):
    teilnehmer_antwort, _ = TeilnehmerAntwort.objects.get_or_create(versuch=versuch, frage=frage)
    if frage.typ in [Frage.Typ.SINGLE_CHOICE, Frage.Typ.MULTIPLE_CHOICE, Frage.Typ.WAHR_FALSCH]:
        antwort_ids = daten.getlist("antworten") if hasattr(daten, "getlist") else daten.get("antworten", [])
        erlaubte_ids = list(frage.antworten.values_list("id", flat=True))
        antworten = Antwort.objects.filter(id__in=antwort_ids).filter(id__in=erlaubte_ids)
        teilnehmer_antwort.ausgewaehlte_antworten.set(antworten)
    elif frage.typ == Frage.Typ.FREITEXT:
        teilnehmer_antwort.freitext_antwort = daten.get("freitext_antwort", "")
    elif frage.typ == Frage.Typ.ZUORDNUNG:
        teilnehmer_antwort.zuordnung_json = daten.get("zuordnung_json", {})
    teilnehmer_antwort.save()
    return teilnehmer_antwort


@transaction.atomic
def werte_versuch_aus(versuch):
    punkte_erreicht = Decimal("0")
    punkte_gesamt = Decimal("0")
    freitext_offen = False

    fragen = Frage.objects.filter(id__in=versuch.fragen_reihenfolge).prefetch_related("antworten", "zuordnungen")
    fragen_map = {frage.id: frage for frage in fragen}
    for frage_id in versuch.fragen_reihenfolge:
        frage = fragen_map.get(frage_id)
        if not frage:
            continue
        antwort, _ = TeilnehmerAntwort.objects.get_or_create(versuch=versuch, frage=frage)
        punkte_gesamt += Decimal(frage.punkte)
        punkte = Decimal("0")
        ist_korrekt = False

        if frage.typ in [Frage.Typ.SINGLE_CHOICE, Frage.Typ.WAHR_FALSCH]:
            richtige_ids = set(frage.antworten.filter(ist_korrekt=True).values_list("id", flat=True))
            gewaehlt_ids = set(antwort.ausgewaehlte_antworten.values_list("id", flat=True))
            ist_korrekt = len(gewaehlt_ids) == 1 and gewaehlt_ids == richtige_ids
            punkte = Decimal(frage.punkte) if ist_korrekt else Decimal("0")
        elif frage.typ == Frage.Typ.MULTIPLE_CHOICE:
            richtige_ids = set(frage.antworten.filter(ist_korrekt=True).values_list("id", flat=True))
            gewaehlt_ids = set(antwort.ausgewaehlte_antworten.values_list("id", flat=True))
            ist_korrekt = gewaehlt_ids == richtige_ids
            punkte = Decimal(frage.punkte) if ist_korrekt else Decimal("0")
        elif frage.typ == Frage.Typ.ZUORDNUNG:
            paare = list(frage.zuordnungen.all())
            mapping = antwort.zuordnung_json or {}
            korrekt = sum(1 for paar in paare if mapping.get(str(paar.id)) == paar.rechtes_element)
            punkte = Decimal(frage.punkte) * Decimal(korrekt) / Decimal(len(paare) or 1)
            ist_korrekt = korrekt == len(paare)
        elif frage.typ == Frage.Typ.FREITEXT:
            if antwort.freitext_punkte is None:
                freitext_offen = True
                ist_korrekt = None
                punkte = Decimal("0")
            else:
                punkte = min(Decimal(antwort.freitext_punkte), Decimal(frage.punkte))
                ist_korrekt = punkte > Decimal("0")
        elif frage.typ == Frage.Typ.SZENARIO:
            teilfragen = frage.teilfragen.all()
            punkte_gesamt -= Decimal(frage.punkte)
            for teilfrage in teilfragen:
                punkte_gesamt += Decimal(teilfrage.punkte)

        antwort.ist_korrekt = ist_korrekt
        antwort.punkte_vergeben = punkte
        antwort.save(update_fields=["ist_korrekt", "punkte_vergeben"])
        punkte_erreicht += punkte

    prozent = Decimal("0") if punkte_gesamt == 0 else (punkte_erreicht / punkte_gesamt) * Decimal("100")
    versuch.punkte_erreicht = punkte_erreicht
    versuch.punkte_gesamt = punkte_gesamt
    versuch.prozent_erreicht = prozent.quantize(Decimal("0.01"))
    versuch.bestanden = versuch.prozent_erreicht >= Decimal(versuch.pruefung.bestehensgrenze_prozent)
    versuch.status = PruefungsVersuch.Status.AUSSTEHEND if freitext_offen else PruefungsVersuch.Status.ABGESCHLOSSEN
    versuch.abgeschlossen_am = timezone.now()
    versuch.save()
    return versuch


def pruefe_zeitlimit(versuch):
    if not versuch.pruefung.zeitlimit_minuten:
        return False
    deadline = versuch.gestartet_am + timezone.timedelta(minutes=versuch.pruefung.zeitlimit_minuten)
    if timezone.now() <= deadline:
        return False
    versuch.status = PruefungsVersuch.Status.ABGELAUFEN
    versuch.abgeschlossen_am = timezone.now()
    versuch.save(update_fields=["status", "abgeschlossen_am"])
    return True
