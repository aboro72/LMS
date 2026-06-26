from django import forms

from apps.organisations.models import Organisation

from .models import Abschnitt, Kurs, Lektion


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
