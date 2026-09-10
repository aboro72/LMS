from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})


from allauth.account.forms import LoginForm as AllauthLoginForm


class BootstrapLoginForm(AllauthLoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["login"].widget.attrs.update({"class": "form-control"})
        self.fields["password"].widget.attrs.update({"class": "form-control"})
        self.fields["remember"].widget.attrs.update({"class": "form-check-input"})

    def clean_login(self):
        login = super().clean_login()
        aliases = {
            "super-admin": "superadmin",
            "superadmin": "superadmin",
            "org-admin": "orgadmin",
            "orgadmin": "orgadmin",
            "trainer": "trainer",
            "pruefer": "examiner",
            "prüfer": "examiner",
            "examiner": "examiner",
            "lernender": "learner",
            "learner": "learner",
        }
        return aliases.get(login.casefold(), login)

    def clean_password(self):
        password = self.cleaned_data["password"]
        return password.strip()
