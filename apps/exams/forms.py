import csv
import json
from io import TextIOWrapper

from django import forms
from django_quill.quill import Quill

from apps.organisations.models import Organisation

from .models import Antwort, Frage, Fragenkatalog, Pruefung, TeilnehmerAntwort, ZuordnungsPaar


class FragenkatalogForm(forms.ModelForm):
    class Meta:
        model = Fragenkatalog
        fields = ("titel", "beschreibung", "organisation")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and not user.is_superuser:
            organisation_ids = user.profile.filter(aktiv=True).values_list("organisation_id", flat=True)
            self.fields["organisation"].queryset = Organisation.objects.filter(id__in=organisation_ids)


class FrageForm(forms.ModelForm):
    class Meta:
        model = Frage
        fields = ("typ", "fragetext", "erklaerung", "schwierigkeit", "punkte", "eltern_szenario")

    def __init__(self, *args, fragenkatalog=None, **kwargs):
        super().__init__(*args, **kwargs)
        if fragenkatalog:
            self.fields["eltern_szenario"].queryset = fragenkatalog.fragen.filter(typ=Frage.Typ.SZENARIO)


class AntwortForm(forms.ModelForm):
    class Meta:
        model = Antwort
        fields = ("antworttext", "ist_korrekt", "reihenfolge")


class ZuordnungsPaarForm(forms.ModelForm):
    class Meta:
        model = ZuordnungsPaar
        fields = ("linkes_element", "rechtes_element", "reihenfolge")


class PruefungForm(forms.ModelForm):
    class Meta:
        model = Pruefung
        fields = (
            "titel",
            "beschreibung",
            "organisation",
            "fragenkatalog",
            "anzahl_fragen",
            "zeitlimit_minuten",
            "bestehensgrenze_prozent",
            "max_versuche",
            "zufaellige_fragenreihenfolge",
            "zufaellige_antwortfolge",
            "kein_zurueck",
            "ist_aktiv",
        )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and not user.is_superuser:
            organisation_ids = user.profile.filter(aktiv=True).values_list("organisation_id", flat=True)
            self.fields["organisation"].queryset = Organisation.objects.filter(id__in=organisation_ids)
            self.fields["fragenkatalog"].queryset = Fragenkatalog.objects.filter(organisation_id__in=organisation_ids)


class CSVImportForm(forms.Form):
    datei = forms.FileField()

    def importiere(self, fragenkatalog):
        handle = TextIOWrapper(self.cleaned_data["datei"].file, encoding="utf-8")
        reader = csv.DictReader(handle, delimiter=";")
        erstellt = 0
        for row in reader:
            frage = Frage.objects.create(
                fragenkatalog=fragenkatalog,
                typ=row["typ"],
                fragetext=Quill(json.dumps({"delta": "", "html": row["fragetext"]})),
                punkte=int(row.get("punkte") or 1),
                schwierigkeit=row.get("schwierigkeit") or Frage.Schwierigkeit.MITTEL,
            )
            if frage.typ in [Frage.Typ.SINGLE_CHOICE, Frage.Typ.MULTIPLE_CHOICE, Frage.Typ.WAHR_FALSCH]:
                for index in range(1, 9):
                    antworttext = row.get(f"antwort_{index}", "").strip()
                    if antworttext:
                        Antwort.objects.create(
                            frage=frage,
                            antworttext=antworttext,
                            ist_korrekt=row.get(f"korrekt_{index}", "0").strip() == "1",
                            reihenfolge=index,
                        )
            elif frage.typ == Frage.Typ.ZUORDNUNG:
                for index in range(1, 6):
                    links = row.get(f"links_{index}", "").strip()
                    rechts = row.get(f"rechts_{index}", "").strip()
                    if links and rechts:
                        ZuordnungsPaar.objects.create(
                            frage=frage,
                            linkes_element=links,
                            rechtes_element=rechts,
                            reihenfolge=index,
                        )
            erstellt += 1
        return erstellt


class FreitextBewertungForm(forms.ModelForm):
    class Meta:
        model = TeilnehmerAntwort
        fields = ("freitext_punkte", "freitext_kommentar")
