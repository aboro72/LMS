from django.conf import settings
from django.test import Client
from django.urls import reverse

from apps.courses.tests import BaseLmsTestCase
from apps.payments.models import Zahlungseinstellungen


class ProductionSmokeTests(BaseLmsTestCase):
    def setUp(self):
        super().setUp()
        if not getattr(settings, "PRODUCTION", False):
            self.skipTest("Wird durch deploy/test_production.py mit Produktionseinstellungen ausgefuehrt.")

    def test_public_pages_under_https(self):
        for name in ("home", "course_catalog", "account_login", "learning_path_list"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name), secure=True)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["X-Content-Type-Options"], "nosniff")
                self.assertIn("max-age=", response["Strict-Transport-Security"])
        self.assertFalse(settings.DEBUG)
        self.assertTrue(settings.SESSION_COOKIE_SECURE)
        self.assertTrue(settings.CSRF_COOKIE_SECURE)

    def test_http_redirects_and_unknown_hosts_are_rejected(self):
        self.assertEqual(self.client.get("/").status_code, 301)
        self.assertEqual(self.client.get("/", secure=True, HTTP_HOST="untrusted.invalid").status_code, 400)

    def test_superadmin_switch_with_real_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.superuser)
        url = reverse("superadmin_payment_settings")
        response = client.get(url, secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies["csrftoken"]["secure"])
        self.assertEqual(client.post(url, {"payment_aktiv": "on"}, secure=True).status_code, 403)
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post(url, {"payment_aktiv": "on", "csrfmiddlewaretoken": token}, secure=True, HTTP_ORIGIN="https://testserver").status_code, 302)
        self.assertTrue(Zahlungseinstellungen.load().payment_aktiv)
        self.assertEqual(client.post(url, {"csrfmiddlewaretoken": token}, secure=True, HTTP_ORIGIN="https://testserver").status_code, 302)
        self.assertFalse(Zahlungseinstellungen.load().payment_aktiv)

    def test_disabled_checkout_and_dashboard_render(self):
        self.client.force_login(self.learner)
        self.assertEqual(self.client.get(reverse("dashboard"), secure=True).status_code, 200)
        url = reverse("course_checkout", kwargs={"slug": self.kurs.slug})
        self.assertContains(self.client.get(url, secure=True), "Zahlungen sind derzeit nicht")
