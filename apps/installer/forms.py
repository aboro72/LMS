from django import forms


class InstallationForm(forms.Form):
    organisation = forms.CharField(label="Name der Organisation", max_length=200)
    slug = forms.SlugField(label="Mandanten-Slug", max_length=50)
    kontakt_email = forms.EmailField(label="Kontakt-E-Mail")
    hostname = forms.CharField(
        label="Domain oder IP-Adresse",
        max_length=255,
        help_text="Zum Beispiel lms.example.de, 203.0.113.10 oder localhost.",
    )
    admin_username = forms.CharField(label="Admin-Benutzername", max_length=150)
    admin_email = forms.EmailField(label="Admin-E-Mail")
    admin_password = forms.CharField(label="Admin-Passwort", min_length=12, widget=forms.PasswordInput)
    admin_password_confirm = forms.CharField(label="Admin-Passwort wiederholen", widget=forms.PasswordInput)

    def clean(self):
        data = super().clean()
        if data.get("admin_password") != data.get("admin_password_confirm"):
            self.add_error("admin_password_confirm", "Die Passwörter stimmen nicht überein.")
        return data
