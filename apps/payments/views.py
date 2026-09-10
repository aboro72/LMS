from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, FormView, ListView

from apps.courses.models import Einschreibung, Kurs

from .forms import CheckoutForm, PaymentSwitchForm
from .models import AuditLog, Auszahlungsstatus, Rechnung, Zahlung, Zahlungsart, Zahlungsstatus
from .services import bestaetige_zahlung, erstelle_zahlung, lade_zahlungseinstellungen, log_audit, zahlungsart_ist_automatisch


class SuperadminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.groups.filter(name="superadmin").exists()


class CheckoutView(LoginRequiredMixin, FormView):
    form_class = CheckoutForm
    template_name = "payments/checkout.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        kurs_queryset = Kurs.objects.filter(slug=kwargs["slug"], ist_veroeffentlicht=True, organisation__aktiv=True)
        if kwargs.get("org_slug"):
            kurs_queryset = kurs_queryset.filter(organisation__slug=kwargs["org_slug"])
        self.kurs = get_object_or_404(kurs_queryset)
        self.org_slug = kwargs.get("org_slug")
        if self.kurs.ist_kostenlos or self.kurs.preis <= 0:
            Einschreibung.objects.update_or_create(
                nutzer=request.user,
                kurs=self.kurs,
                defaults={"bezahlt": True},
            )
            messages.success(request, "Du bist in den kostenlosen Kurs eingeschrieben.")
            if self.org_slug:
                return redirect("tenant_course_learn", org_slug=self.kurs.organisation.slug, slug=self.kurs.slug)
            return redirect("course_learn", slug=self.kurs.slug)
        if Einschreibung.objects.filter(nutzer=request.user, kurs=self.kurs, bezahlt=True).exists():
            if self.org_slug:
                return redirect("tenant_course_learn", org_slug=self.kurs.organisation.slug, slug=self.kurs.slug)
            return redirect("course_learn", slug=self.kurs.slug)
        self.payment_settings = lade_zahlungseinstellungen()
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["payment_settings"] = self.payment_settings
        return kwargs

    def form_valid(self, form):
        zahlungsart = form.cleaned_data["zahlungsart"]
        if zahlungsart not in dict(self.payment_settings.aktive_zahlungsarten()):
            messages.error(self.request, "Diese Zahlungsart ist aktuell nicht aktiviert.")
            return self.form_invalid(form)
        zahlung = erstelle_zahlung(self.kurs, self.request.user, zahlungsart)
        if settings.DEBUG and zahlungsart_ist_automatisch(zahlungsart) and self.payment_settings.demo_autoconfirm:
            bestaetige_zahlung(zahlung, provider_referenz=f"demo-{zahlungsart}-{zahlung.zahlung_id}", actor=self.request.user)
            messages.success(self.request, "Zahlung wurde bestaetigt. Der Kurs ist freigeschaltet.")
            if self.org_slug:
                return redirect("tenant_course_learn", org_slug=self.kurs.organisation.slug, slug=self.kurs.slug)
            return redirect("course_learn", slug=self.kurs.slug)
        if zahlungsart == Zahlungsart.BANK_TRANSFER:
            messages.warning(self.request, "Ueberweisung wurde vorgemerkt. Zugriff wird nach Zahlungseingang freigeschaltet.")
            return redirect("payment_success", zahlung_id=zahlung.zahlung_id)
        return redirect("payment_success", zahlung_id=zahlung.zahlung_id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        gebuehr, trainer_anteil = Zahlung.berechne_aufteilung(self.kurs.preis)
        context.update(
            {
                "kurs": self.kurs,
                "plattform_gebuehr": gebuehr,
                "trainer_anteil": trainer_anteil,
                "payment_settings": self.payment_settings,
                "has_payment_methods": bool(self.payment_settings.aktive_zahlungsarten()),
            }
        )
        return context


class PaymentSuccessView(LoginRequiredMixin, DetailView):
    model = Zahlung
    template_name = "payments/status.html"
    context_object_name = "zahlung"
    slug_field = "zahlung_id"
    slug_url_kwarg = "zahlung_id"

    def get_queryset(self):
        return Zahlung.objects.filter(nutzer=self.request.user).select_related("kurs", "trainer")


class PaymentCancelView(LoginRequiredMixin, View):
    def post(self, request, zahlung_id):
        zahlung = get_object_or_404(Zahlung, zahlung_id=zahlung_id, nutzer=request.user)
        if zahlung.status == Zahlungsstatus.OFFEN:
            zahlung.status = Zahlungsstatus.STORNIERT
            zahlung.save(update_fields=["status"])
            log_audit(actor=request.user, organisation=zahlung.kurs.organisation, action="zahlung_storniert", obj=zahlung, message="Zahlung wurde durch Nutzer storniert.")
        messages.warning(request, "Zahlung wurde abgebrochen.")
        return redirect("course_detail", slug=zahlung.kurs.slug)


class TrainerPayoutListView(SuperadminRequiredMixin, ListView):
    model = Zahlung
    template_name = "payments/superadmin/payouts.html"
    context_object_name = "zahlungen"

    def get_queryset(self):
        return (
            Zahlung.objects.filter(
                Q(status=Zahlungsstatus.BEZAHLT)
                | Q(status=Zahlungsstatus.OFFEN, zahlungsart=Zahlungsart.BANK_TRANSFER)
            )
            .select_related("trainer", "kurs", "nutzer")
            .order_by("trainer__username", "-bezahlt_am")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        offene_zahlungen = self.get_queryset().filter(
            status=Zahlungsstatus.BEZAHLT,
            auszahlungsstatus__in=[Auszahlungsstatus.OFFEN, Auszahlungsstatus.GEMELDET],
        )
        context["trainer_summen"] = (
            offene_zahlungen.values("trainer_id", "trainer__username", "trainer__email")
            .annotate(
                brutto=Sum("betrag_brutto"),
                gebuehr=Sum("plattform_gebuehr"),
                auszuzahlen=Sum("trainer_anteil"),
            )
            .order_by("trainer__username")
        )
        return context


class BankTransferConfirmView(SuperadminRequiredMixin, View):
    def post(self, request, zahlung_id):
        zahlung = get_object_or_404(Zahlung, zahlung_id=zahlung_id, zahlungsart=Zahlungsart.BANK_TRANSFER)
        bestaetige_zahlung(zahlung, provider_referenz="manual-bank-transfer", actor=request.user)
        messages.success(request, "Ueberweisung bestaetigt und Kurs freigeschaltet.")
        return redirect("superadmin_payouts")


class PayoutMarkNotifiedView(SuperadminRequiredMixin, View):
    def post(self, request, zahlung_id):
        zahlung = get_object_or_404(Zahlung, zahlung_id=zahlung_id, status=Zahlungsstatus.BEZAHLT)
        zahlung.auszahlungsstatus = Auszahlungsstatus.GEMELDET
        zahlung.betreiber_notiz = "Betreiber wurde ueber die auszuzahlende Summe informiert."
        zahlung.save(update_fields=["auszahlungsstatus", "betreiber_notiz"])
        log_audit(actor=request.user, organisation=zahlung.kurs.organisation, action="auszahlung_gemeldet", obj=zahlung, message="Auszahlung wurde als gemeldet markiert.")
        messages.success(request, "Zahlung wurde als gemeldet markiert.")
        return redirect("superadmin_payouts")


class PayoutMarkPaidView(SuperadminRequiredMixin, View):
    def post(self, request, zahlung_id):
        zahlung = get_object_or_404(Zahlung, zahlung_id=zahlung_id, status=Zahlungsstatus.BEZAHLT)
        zahlung.auszahlungsstatus = Auszahlungsstatus.AUSGEZAHLT
        zahlung.ausgezahlt_am = timezone.now()
        zahlung.save(update_fields=["auszahlungsstatus", "ausgezahlt_am"])
        log_audit(actor=request.user, organisation=zahlung.kurs.organisation, action="auszahlung_ausgezahlt", obj=zahlung, message="Auszahlung wurde als ausgezahlt markiert.")
        messages.success(request, "Zahlung wurde als ausgezahlt markiert.")
        return redirect("superadmin_payouts")


class RechnungDetailView(LoginRequiredMixin, DetailView):
    model = Rechnung
    template_name = "payments/invoice.html"
    context_object_name = "rechnung"
    slug_field = "rechnungsnummer"
    slug_url_kwarg = "rechnungsnummer"

    def get_queryset(self):
        queryset = Rechnung.objects.select_related("zahlung", "zahlung__kurs", "zahlung__nutzer")
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(zahlung__nutzer=self.request.user)


class AuditLogListView(SuperadminRequiredMixin, ListView):
    model = AuditLog
    template_name = "payments/superadmin/audit_log.html"
    context_object_name = "logs"
    paginate_by = 50

    def get_queryset(self):
        queryset = AuditLog.objects.select_related("actor", "organisation")
        action = self.request.GET.get("action", "").strip()
        if action:
            queryset = queryset.filter(action=action)
        return queryset

class PaymentSettingsView(SuperadminRequiredMixin, FormView):
    template_name = "payments/superadmin/settings.html"
    form_class = PaymentSwitchForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = lade_zahlungseinstellungen()
        return kwargs

    def form_valid(self, form):
        form.save()
        log_audit(actor=self.request.user, action="payment_schalter_geaendert",
                  obj=form.instance, metadata={"payment_aktiv": form.instance.payment_aktiv})
        messages.success(self.request, "Zahlungseinstellungen gespeichert.")
        return redirect("superadmin_payment_settings")
