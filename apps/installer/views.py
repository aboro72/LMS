from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from apps.accounts.models import Rolle, UserProfile
from apps.organisations.models import Organisation, OrganisationDomain

from .forms import InstallationForm
from .models import InstallationState


class InstallationView(View):
    template_name = "installer/setup.html"

    def dispatch(self, request, *args, **kwargs):
        token = request.GET.get("token") or request.session.get("installer_token")
        expected = getattr(settings, "INSTALLER_TOKEN", "")
        if not expected or token != expected:
            raise PermissionDenied
        request.session["installer_token"] = token
        if InstallationState.objects.filter(completed_at__isnull=False).exists():
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(request, self.template_name, {"form": InstallationForm()})

    @transaction.atomic
    def post(self, request):
        form = InstallationForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        if Organisation.objects.exists() or get_user_model().objects.exists():
            raise PermissionDenied("Die Installation wurde bereits begonnen.")
        data = form.cleaned_data
        org = Organisation.objects.create(
            name=data["organisation"], slug=data["slug"], kontakt_email=data["kontakt_email"]
        )
        OrganisationDomain.objects.create(organisation=org, hostname=data["hostname"], primaer=True)
        user = get_user_model().objects.create_superuser(
            username=data["admin_username"], email=data["admin_email"], password=data["admin_password"]
        )
        UserProfile.objects.create(nutzer=user, organisation=org, rolle=Rolle.ORG_ADMIN)
        InstallationState.objects.create(completed_at=timezone.now())
        request.session.flush()
        return render(request, "installer/complete.html", {"organisation": org})
