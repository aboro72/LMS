from django.contrib import admin

from .models import Auszahlungsstatus, Zahlung, Zahlungseinstellungen, Zahlungsstatus


@admin.register(Zahlungseinstellungen)
class ZahlungseinstellungenAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Allgemein", {"fields": ("demo_autoconfirm", "ueberweisung_aktiv")}),
        ("Stripe und Google Pay", {"fields": ("stripe_aktiv", "stripe_public_key", "stripe_secret_key", "google_pay_aktiv")}),
        ("PayPal", {"fields": ("paypal_aktiv", "paypal_client_id", "paypal_secret")}),
        ("Ueberweisung", {"fields": ("kontoinhaber", "iban", "bic", "bankname")}),
    )

    def has_add_permission(self, request):
        return not Zahlungseinstellungen.objects.exists()


@admin.register(Zahlung)
class ZahlungAdmin(admin.ModelAdmin):
    list_display = (
        "zahlung_id",
        "nutzer",
        "kurs",
        "trainer",
        "zahlungsart",
        "status",
        "betrag_brutto",
        "trainer_anteil",
        "auszahlungsstatus",
        "bezahlt_am",
    )
    list_filter = ("zahlungsart", "status", "auszahlungsstatus", "kurs__organisation")
    search_fields = ("zahlung_id", "nutzer__username", "kurs__titel", "trainer__username", "provider_referenz")
    readonly_fields = ("zahlung_id", "plattform_gebuehr", "trainer_anteil", "erstellt_am", "bezahlt_am")
    actions = ("markiere_betreiber_informiert", "markiere_ausgezahlt")

    @admin.action(description="Betreiber als informiert markieren")
    def markiere_betreiber_informiert(self, request, queryset):
        queryset.filter(status=Zahlungsstatus.BEZAHLT).update(auszahlungsstatus=Auszahlungsstatus.GEMELDET)

    @admin.action(description="Als ausgezahlt markieren")
    def markiere_ausgezahlt(self, request, queryset):
        from django.utils import timezone

        queryset.filter(status=Zahlungsstatus.BEZAHLT).update(
            auszahlungsstatus=Auszahlungsstatus.AUSGEZAHLT,
            ausgezahlt_am=timezone.now(),
        )
