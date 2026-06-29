from django.urls import path

from .views import (
    AuditLogListView,
    BankTransferConfirmView,
    CheckoutView,
    PaymentCancelView,
    PaymentSuccessView,
    PayoutMarkNotifiedView,
    PayoutMarkPaidView,
    RechnungDetailView,
    TrainerPayoutListView,
)


urlpatterns = [
    path("kurse/<slug:slug>/checkout/", CheckoutView.as_view(), name="course_checkout"),
    path("zahlungen/<uuid:zahlung_id>/success/", PaymentSuccessView.as_view(), name="payment_success"),
    path("zahlungen/<uuid:zahlung_id>/cancel/", PaymentCancelView.as_view(), name="payment_cancel"),
    path("rechnungen/<slug:rechnungsnummer>/", RechnungDetailView.as_view(), name="invoice_detail"),
    path("superadmin/auszahlungen/", TrainerPayoutListView.as_view(), name="superadmin_payouts"),
    path("superadmin/audit-log/", AuditLogListView.as_view(), name="superadmin_audit_log"),
    path("superadmin/zahlungen/<uuid:zahlung_id>/ueberweisung-bestaetigen/", BankTransferConfirmView.as_view(), name="bank_transfer_confirm"),
    path("superadmin/zahlungen/<uuid:zahlung_id>/gemeldet/", PayoutMarkNotifiedView.as_view(), name="payout_mark_notified"),
    path("superadmin/zahlungen/<uuid:zahlung_id>/ausgezahlt/", PayoutMarkPaidView.as_view(), name="payout_mark_paid"),
]
