from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.test import Client, override_settings
from django.urls import reverse

from apps.accounts.models import Rolle
from apps.courses.tests import BaseLmsTestCase
from apps.courses.models import Einschreibung
from .models import AuditLog, OrganisationZahlungseinstellungen, Zahlung, Zahlungsart, Zahlungseinstellungen
from .services import erstelle_zahlung


class PaymentSwitchTests(BaseLmsTestCase):
    def test_disabled_by_default_and_service_rejects_payment(self):
        config = Zahlungseinstellungen.load()
        self.assertFalse(config.payment_aktiv)
        self.assertEqual(config.aktive_zahlungsarten(), [])
        with self.assertRaises(PermissionDenied):
            erstelle_zahlung(self.kurs, self.learner, Zahlungsart.BANK_TRANSFER)
        self.assertFalse(Zahlung.objects.exists())

    def test_disabled_checkout_get_and_forged_post(self):
        self.client.force_login(self.learner)
        url = reverse("course_checkout", kwargs={"slug": self.kurs.slug})
        self.assertContains(self.client.get(url), "Zahlungen sind derzeit nicht")
        self.assertEqual(self.client.post(url, {"zahlungsart": "bank_transfer"}).status_code, 200)
        self.assertFalse(Zahlung.objects.exists())
        self.assertFalse(Einschreibung.objects.filter(kurs=self.kurs, nutzer=self.learner).exists())
        detail = self.client.get(reverse("course_detail", kwargs={"slug": self.kurs.slug}))
        self.assertNotContains(detail, "Kurs kaufen")

    def test_anonymous_checkout_redirects_without_creating_enrollment(self):
        for course in (self.kurs, self.free_course):
            url = reverse("course_checkout", kwargs={"slug": course.slug})
            for method in (self.client.get, self.client.post):
                self.assertEqual(method(url).status_code, 302)
        self.assertFalse(Einschreibung.objects.exists())

    def test_free_and_existing_paid_access_remain_available(self):
        self.client.force_login(self.learner)
        url = reverse("course_checkout", kwargs={"slug": self.free_course.slug})
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertTrue(Einschreibung.objects.filter(kurs=self.free_course, nutzer=self.learner, bezahlt=True).exists())
        Einschreibung.objects.create(kurs=self.kurs, nutzer=self.learner, bezahlt=True)
        url = reverse("course_checkout", kwargs={"slug": self.kurs.slug})
        self.assertRedirects(self.client.get(url), reverse("course_learn", kwargs={"slug": self.kurs.slug}))

    def test_org_admin_configures_own_bank_transfer_without_affecting_other_orgs(self):
        url = reverse("superadmin_payment_settings")
        for user in (self.learner, self.trainer, self.org_admin):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {"payment_aktiv": "on"}).status_code, 403)
        self.assertFalse(Zahlungseinstellungen.load().payment_aktiv)
        org_url = reverse("org_payment_settings", kwargs={"slug": self.org.slug})
        self.client.force_login(self.org_admin)
        self.assertEqual(self.client.get(org_url).status_code, 200)
        self.assertRedirects(self.client.post(org_url, {
            "payment_aktiv": "on", "ueberweisung_aktiv": "on", "iban": "DE89370400440532013000",
        }), org_url)
        self.assertTrue(OrganisationZahlungseinstellungen.objects.get(organisation=self.org).payment_aktiv)
        self.client.force_login(self.learner)
        checkout = reverse("course_checkout", kwargs={"slug": self.kurs.slug})
        self.assertEqual(self.client.post(checkout, {"zahlungsart": "bank_transfer"}).status_code, 302)
        self.assertEqual(Zahlung.objects.count(), 1)
        self.assertEqual(Zahlung.objects.first().kurs.organisation, self.org)

    def test_superadmin_group_can_use_switch(self):
        self.other.groups.add(Group.objects.get(name=Rolle.SUPERADMIN))
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("superadmin_payment_settings"), {"payment_aktiv": "on"}).status_code, 302)
        self.assertTrue(Zahlungseinstellungen.load().payment_aktiv)

    def test_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.superuser)
        self.assertEqual(client.post(reverse("superadmin_payment_settings"), {"payment_aktiv": "on"}).status_code, 403)
        self.assertFalse(Zahlungseinstellungen.load().payment_aktiv)

    def test_staff_model_permission_cannot_bypass_switch_restriction(self):
        config = Zahlungseinstellungen.load()
        self.other.is_staff = True
        self.other.save()
        self.other.user_permissions.add(Permission.objects.get(codename="change_zahlungseinstellungen"))
        self.client.force_login(self.other)
        url = reverse("admin:payments_zahlungseinstellungen_change", args=[config.pk])
        self.assertEqual(self.client.post(url, {"payment_aktiv": "on"}).status_code, 403)
        self.assertFalse(Zahlungseinstellungen.load().payment_aktiv)

    @override_settings(DEBUG=False)
    def test_production_never_offers_demo_providers(self):
        config = Zahlungseinstellungen.load()
        config.payment_aktiv = True
        config.demo_autoconfirm = True
        config.stripe_aktiv = True
        config.paypal_aktiv = True
        config.google_pay_aktiv = True
        config.save()
        self.assertEqual(config.aktive_zahlungsarten(), [(Zahlungsart.BANK_TRANSFER, Zahlungsart.BANK_TRANSFER.label)])
        with self.assertRaises(PermissionDenied):
            erstelle_zahlung(self.kurs, self.learner, Zahlungsart.STRIPE)
