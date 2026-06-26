from django import forms
from django.core.exceptions import ValidationError

from apps.organisations.models import Organisation

from .models import Abschnitt, Begleitmaterial, Kurs, Lektion, Uebungsantwort, Uebungsfrage


class KursForm(forms.ModelForm):
    class Meta:
        model = Kurs
        fields = (
            "titel",
            "slug",
            "beschreibung",
            "thumbnail",
            "organisation",
            "sprache",
            "niveau",
            "ist_veroeffentlicht",
            "ist_kostenlos",
            "preis",
        )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and not user.is_superuser:
            organisation_ids = user.profile.filter(aktiv=True).values_list("organisation_id", flat=True)
            self.fields["organisation"].queryset = Organisation.objects.filter(id__in=organisation_ids)


class AbschnittForm(forms.ModelForm):
    class Meta:
        model = Abschnitt
        fields = ("titel", "reihenfolge", "ist_veroeffentlicht")


class LektionForm(forms.ModelForm):
    VIDEO_EXTENSIONS = (".mp4", ".webm", ".mov", ".m4v")

    class Meta:
        model = Lektion
        fields = (
            "titel",
            "typ",
            "reihenfolge",
            "inhalt",
            "video_url",
            "datei",
            "dauer_minuten",
            "ist_vorschau",
        )
        labels = {
            "typ": "Lektionstyp",
            "inhalt": "Begleittext",
            "video_url": "Video-URL",
            "datei": "Upload-Datei",
            "dauer_minuten": "Dauer in Minuten",
            "ist_vorschau": "Kostenlose Vorschau",
        }
        help_texts = {
            "video_url": "Optional fuer externe Videoquellen. Fuer Selfhosting bevorzugt: Video als Datei hochladen.",
            "datei": "Bei Video-Lektionen MP4, WebM, MOV oder M4V hochladen. Bei Dokumenten PDF oder andere Kursdateien.",
            "inhalt": "Optionaler Text unter dem Video oder Dokument.",
        }

    def clean(self):
        cleaned_data = super().clean()
        lesson_type = cleaned_data.get("typ")
        uploaded_file = cleaned_data.get("datei")
        video_url = cleaned_data.get("video_url")
        if lesson_type == Lektion.Typ.VIDEO and not uploaded_file and not video_url and not self.instance.datei:
            raise ValidationError("Video-Lektionen benoetigen eine Video-URL oder eine hochgeladene Videodatei.")
        if lesson_type == Lektion.Typ.VIDEO and uploaded_file:
            filename = uploaded_file.name.lower()
            if not filename.endswith(self.VIDEO_EXTENSIONS):
                raise ValidationError("Video-Uploads muessen MP4, WebM, MOV oder M4V sein.")
        return cleaned_data


class BegleitmaterialForm(forms.ModelForm):
    class Meta:
        model = Begleitmaterial
        fields = ("titel", "datei", "reihenfolge")


class UebungsfrageForm(forms.ModelForm):
    class Meta:
        model = Uebungsfrage
        fields = ("frage", "erklaerung", "reihenfolge", "aktiv")
        widgets = {
            "frage": forms.Textarea(attrs={"rows": 3}),
            "erklaerung": forms.Textarea(attrs={"rows": 3}),
        }


class UebungsantwortForm(forms.ModelForm):
    class Meta:
        model = Uebungsantwort
        fields = ("antwort", "ist_korrekt", "reihenfolge")
