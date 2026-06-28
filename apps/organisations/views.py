from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView

from apps.accounts.mixins import RollenMixin
from apps.accounts.models import Rolle, UserProfile
from apps.payments.models import Zahlung

from .forms import (
    EinladungForm,
    OrganisationDesignForm,
    OrganisationEmailKonfigForm,
    OrganisationSignupForm,
    OrganisationStartseiteForm,
)
from .models import (
    Einladung,
    Organisation,
    OrganisationDesign,
    OrganisationEmailKonfiguration,
    OrganisationStartseite,
)


# --------------------------------------------------------------------------- #
# Hilfsmethode: Organisation für Org-Admin laden
# --------------------------------------------------------------------------- #
def _get_org_for_admin(request, slug):
    if request.user.is_superuser:
        return get_object_or_404(Organisation, slug=slug)
    org_ids = request.user.profile.filter(
        rolle=Rolle.ORG_ADMIN, aktiv=True
    ).values_list("organisation_id", flat=True)
    return get_object_or_404(Organisation, slug=slug, id__in=org_ids)


# --------------------------------------------------------------------------- #
# Org-Signup
# --------------------------------------------------------------------------- #
class OrganisationSignupView(LoginRequiredMixin, CreateView):
    form_class = OrganisationSignupForm
    template_name = "organisations/signup.html"

    def form_valid(self, form):
        org = form.save()
        UserProfile.objects.create(nutzer=self.request.user, organisation=org, rolle=Rolle.ORG_ADMIN)
        messages.success(self.request, f"Organisation '{org.name}' wurde erstellt.")
        return redirect("org_admin_dashboard", slug=org.slug)


# --------------------------------------------------------------------------- #
# Org-Admin Dashboard
# --------------------------------------------------------------------------- #
class OrgAdminDashboardView(RollenMixin, TemplateView):
    rolle = Rolle.ORG_ADMIN
    template_name = "organisations/org_admin.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.courses.models import Einschreibung, Kurs

        org = _get_org_for_admin(self.request, self.kwargs["slug"])
        nutzer_count = (
            UserProfile.objects.filter(organisation=org, aktiv=True)
            .values("nutzer").distinct().count()
        )
        kurs_count = Kurs.objects.filter(organisation=org).count()
        einschreibungen_count = Einschreibung.objects.filter(
            kurs__organisation=org, bezahlt=True
        ).count()
        umsatz = (
            Zahlung.objects.filter(kurs__organisation=org, status="BEZAHLT")
            .aggregate(total=Sum("betrag_brutto"))["total"] or 0
        )
        trainer_anteil = (
            Zahlung.objects.filter(kurs__organisation=org, status="BEZAHLT")
            .aggregate(total=Sum("trainer_anteil"))["total"] or 0
        )
        top_kurse = (
            Kurs.objects.filter(organisation=org, ist_veroeffentlicht=True)
            .annotate(anmeldungen=Count("einschreibung"))
            .order_by("-anmeldungen")[:5]
        )
        context.update({
            "org": org,
            "nutzer_count": nutzer_count,
            "kurs_count": kurs_count,
            "einschreibungen_count": einschreibungen_count,
            "umsatz": umsatz,
            "trainer_anteil": trainer_anteil,
            "top_kurse": top_kurse,
        })
        return context


# --------------------------------------------------------------------------- #
# Mitgliederverwaltung
# --------------------------------------------------------------------------- #
class OrgMemberListView(RollenMixin, ListView):
    rolle = Rolle.ORG_ADMIN
    template_name = "organisations/members.html"
    context_object_name = "mitglieder"

    def get_queryset(self):
        self.org = _get_org_for_admin(self.request, self.kwargs["slug"])
        return UserProfile.objects.filter(
            organisation=self.org, aktiv=True
        ).select_related("nutzer").order_by("rolle", "nutzer__username")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["org"] = self.org
        context["einladung_form"] = EinladungForm()
        context["offene_einladungen"] = Einladung.objects.filter(
            organisation=self.org, akzeptiert_am__isnull=True
        ).order_by("-erstellt_am")
        return context


class OrgEinladungCreateView(RollenMixin, View):
    rolle = Rolle.ORG_ADMIN

    def post(self, request, slug):
        org = _get_org_for_admin(request, slug)
        if org.max_nutzer and org.max_nutzer > 0:
            aktuell = (
                UserProfile.objects.filter(organisation=org, aktiv=True)
                .values("nutzer").distinct().count()
            )
            if aktuell >= org.max_nutzer:
                messages.error(
                    request,
                    f"Nutzerlimit ({org.max_nutzer}) der Lizenz erreicht. "
                    "Bitte upgraden Sie Ihre Lizenz.",
                )
                return redirect("org_members", slug=slug)

        form = EinladungForm(request.POST)
        if form.is_valid():
            Einladung.objects.create(
                organisation=org,
                email=form.cleaned_data["email"],
                rolle=form.cleaned_data["rolle"],
                eingeladen_von=request.user,
            )
            messages.success(request, f"Einladung für {form.cleaned_data['email']} erstellt.")
        else:
            messages.error(request, "Einladung konnte nicht erstellt werden.")
        return redirect("org_members", slug=slug)


# --------------------------------------------------------------------------- #
# E-Mail-Konfiguration
# --------------------------------------------------------------------------- #
class OrgEmailKonfigView(RollenMixin, View):
    rolle = Rolle.ORG_ADMIN

    def _ctx(self, org, form):
        return {"form": form, "org": org}

    def get(self, request, slug):
        org = _get_org_for_admin(request, slug)
        config, _ = OrganisationEmailKonfiguration.objects.get_or_create(organisation=org)
        return render(request, "organisations/email_config.html",
                      self._ctx(org, OrganisationEmailKonfigForm(instance=config)))

    def post(self, request, slug):
        org = _get_org_for_admin(request, slug)
        config, _ = OrganisationEmailKonfiguration.objects.get_or_create(organisation=org)
        form = OrganisationEmailKonfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "E-Mail-Konfiguration wurde gespeichert.")
            return redirect("org_email_config", slug=slug)
        return render(request, "organisations/email_config.html", self._ctx(org, form))


# --------------------------------------------------------------------------- #
# Organisations-Design (Kurs-Katalog und Kurs-Seiten)
# --------------------------------------------------------------------------- #
class OrgDesignView(RollenMixin, View):
    rolle = Rolle.ORG_ADMIN

    def _ctx(self, org, form):
        return {"form": form, "org": org}

    def get(self, request, slug):
        org = _get_org_for_admin(request, slug)
        design, _ = OrganisationDesign.objects.get_or_create(organisation=org)
        return render(request, "organisations/design_editor.html",
                      self._ctx(org, OrganisationDesignForm(instance=design)))

    def post(self, request, slug):
        org = _get_org_for_admin(request, slug)
        design, _ = OrganisationDesign.objects.get_or_create(organisation=org)
        form = OrganisationDesignForm(request.POST, request.FILES, instance=design)
        if form.is_valid():
            form.save()
            messages.success(request, "Design gespeichert.")
            return redirect("org_design", slug=slug)
        return render(request, "organisations/design_editor.html", self._ctx(org, form))


# --------------------------------------------------------------------------- #
# Organisations-Startseite (WYSIWYG)
# --------------------------------------------------------------------------- #
class OrgStartseiteView(RollenMixin, View):
    rolle = Rolle.ORG_ADMIN

    def _ctx(self, org, form):
        return {"form": form, "org": org}

    def get(self, request, slug):
        org = _get_org_for_admin(request, slug)
        seite, _ = OrganisationStartseite.objects.get_or_create(organisation=org)
        return render(request, "organisations/startseite_editor.html",
                      self._ctx(org, OrganisationStartseiteForm(instance=seite)))

    def post(self, request, slug):
        org = _get_org_for_admin(request, slug)
        seite, _ = OrganisationStartseite.objects.get_or_create(organisation=org)
        form = OrganisationStartseiteForm(request.POST, request.FILES, instance=seite)
        if form.is_valid():
            form.save()
            messages.success(request, "Startseite gespeichert.")
            return redirect("org_startseite", slug=slug)
        return render(request, "organisations/startseite_editor.html", self._ctx(org, form))


# --------------------------------------------------------------------------- #
# Öffentliche Organisations-Startseite
# --------------------------------------------------------------------------- #
class OffentlicheStartseiteView(TemplateView):
    template_name = "organisations/public_home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.courses.models import Kurs

        org = get_object_or_404(Organisation, slug=self.kwargs["slug"], aktiv=True)
        try:
            startseite = org.startseite if org.startseite.aktiv else None
        except OrganisationStartseite.DoesNotExist:
            startseite = None
        try:
            org_design = org.design
        except OrganisationDesign.DoesNotExist:
            org_design = None

        kurse = (
            Kurs.objects.filter(organisation=org, ist_veroeffentlicht=True)
            .order_by("-erstellt_am")[:6]
        )
        context.update({
            "org": org,
            "startseite": startseite,
            "org_design": org_design,
            "kurse": kurse,
        })
        return context


# --------------------------------------------------------------------------- #
# Superadmin-Übersicht
# --------------------------------------------------------------------------- #
class SuperadminOrganisationenView(LoginRequiredMixin, ListView):
    template_name = "organisations/superadmin_overview.html"
    context_object_name = "organisationen"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Organisation.objects.annotate(
            mitglieder_count=Count("userprofile", distinct=True),
            kurs_count=Count("kurs", distinct=True),
        ).order_by("name")
