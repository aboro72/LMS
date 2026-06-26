from django import forms

from .models import Zahlungsart


class CheckoutForm(forms.Form):
    zahlungsart = forms.ChoiceField(
        choices=Zahlungsart.choices,
        widget=forms.RadioSelect,
        label="Zahlungsart",
    )

    def __init__(self, *args, payment_settings=None, **kwargs):
        super().__init__(*args, **kwargs)
        if payment_settings:
            self.fields["zahlungsart"].choices = payment_settings.aktive_zahlungsarten()
