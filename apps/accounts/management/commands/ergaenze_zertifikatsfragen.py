from html import unescape

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.html import strip_tags

from apps.exams.models import Frage
from .create_demo_data import PRUEFUNGSFRAGEN, quill_html


class Command(BaseCommand):
    help = "Ergaenzt fehlende Erklaerungen der ABoroLMS-Zertifikatsfragen ohne Fragen neu anzulegen."

    def add_arguments(self, parser):
        parser.add_argument("--organisation", default="demo-organisation")

    @transaction.atomic
    def handle(self, *args, **options):
        vorlagen = {(daten["typ"], daten["text"]): daten for daten in PRUEFUNGSFRAGEN}
        fragen = Frage.objects.filter(
            fragenkatalog__titel="ABoroLMS Zertifikatsfragen",
            fragenkatalog__organisation__slug=options["organisation"],
        )
        aktualisiert = 0
        unbekannt = 0
        for frage in fragen:
            text = unescape(strip_tags(frage.fragetext.html)).strip()
            daten = vorlagen.get((frage.typ, text))
            if daten is None:
                unbekannt += 1
                continue
            felder = []
            if not unescape(strip_tags(frage.erklaerung.html or "")).strip():
                frage.erklaerung = quill_html("<p>" + daten["erklaerung"] + "</p>")
                felder.append("erklaerung")
            if daten.get("bewertungshinweis") and not unescape(strip_tags(frage.bewertungshinweis.html or "")).strip():
                frage.bewertungshinweis = quill_html(daten["bewertungshinweis"])
                felder.append("bewertungshinweis")
            if felder:
                frage.save(update_fields=felder)
                aktualisiert += 1
        self.stdout.write(self.style.SUCCESS(f"{aktualisiert} Fragen ergaenzt; {unbekannt} unbekannte Fragen unveraendert."))
