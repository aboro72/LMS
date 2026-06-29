from pathlib import Path

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.accounts.models import Rolle
from apps.organisations.models import Organisation

from .models import Abschnitt, Begleitmaterial, Kurs, KursBewertung, Lektion, Uebungsantwort, Uebungsfrage


def _validate_upload(uploaded_file, allowed_extensions, max_mb, label):
    if not uploaded_file:
        return
    suffix = Path(uploaded_file.name).suffix.lower()
    allowed = tuple(ext.lower() for ext in allowed_extensions)
    if suffix not in allowed:
        raise ValidationError(f"{label} erlaubt nur folgende Dateitypen: {', '.join(allowed)}.")
    max_bytes = max_mb * 1024 * 1024
    if uploaded_file.size > max_bytes:
        raise ValidationError(f"{label} darf maximal {max_mb} MB gross sein.")


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
            organisation_ids = user.profile.filter(rolle=Rolle.TRAINER, aktiv=True).values_list("organisation_id", flat=True)
            self.fields["organisation"].queryset = Organisation.objects.filter(id__in=organisation_ids)

    def clean_thumbnail(self):
        thumbnail = self.cleaned_data.get("thumbnail")
        _validate_upload(
            thumbnail,
            settings.ALLOWED_IMAGE_EXTENSIONS,
            settings.MAX_IMAGE_UPLOAD_MB,
            "Thumbnail",
        )
        return thumbnail


class AbschnittForm(forms.ModelForm):
    class Meta:
        model = Abschnitt
        fields = ("titel", "reihenfolge", "ist_veroeffentlicht")


class LektionForm(forms.ModelForm):
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
        if uploaded_file:
            if lesson_type == Lektion.Typ.VIDEO:
                _validate_upload(
                    uploaded_file,
                    settings.ALLOWED_VIDEO_EXTENSIONS,
                    settings.MAX_VIDEO_UPLOAD_MB,
                    "Video-Upload",
                )
            else:
                _validate_upload(
                    uploaded_file,
                    settings.ALLOWED_DOCUMENT_EXTENSIONS,
                    settings.MAX_DOCUMENT_UPLOAD_MB,
                    "Lektionsdatei",
                )
        return cleaned_data


class BegleitmaterialForm(forms.ModelForm):
    class Meta:
        model = Begleitmaterial
        fields = ("titel", "datei", "reihenfolge")

    def clean_datei(self):
        datei = self.cleaned_data.get("datei")
        _validate_upload(
            datei,
            settings.ALLOWED_DOCUMENT_EXTENSIONS,
            settings.MAX_DOCUMENT_UPLOAD_MB,
            "Begleitmaterial",
        )
        return datei


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

class KursBewertungForm(forms.ModelForm):
    class Meta:
        model = KursBewertung
        fields = ("sterne", "kommentar")
        widgets = {
            "sterne": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 5}),
            "kommentar": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }