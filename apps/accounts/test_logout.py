from django.contrib.auth import SESSION_KEY, get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.organisations.models import Organisation


class OrganisationLogoutTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(
            name="Demo Organisation", slug="demo-organisation",
            kontakt_email="demo@example.com",
        )
        self.user = get_user_model().objects.create_user(username="logout-user")
        self.client.force_login(self.user)

    def set_active_organisation(self, organisation_id):
        session = self.client.session
        session["active_organisation_id"] = organisation_id
        session.save()

    def test_logout_returns_to_organisation_and_clears_session(self):
        self.set_active_organisation(self.organisation.pk)

        response = self.client.post(reverse("account_logout"))

        self.assertRedirects(response, "/demo-organisation/", fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertNotIn("active_organisation_id", self.client.session)

    def test_logout_without_organisation_returns_home(self):
        response = self.client.post(reverse("account_logout"))

        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_logout_with_inactive_organisation_returns_home(self):
        self.set_active_organisation(self.organisation.pk)
        self.organisation.aktiv = False
        self.organisation.save(update_fields=["aktiv"])

        response = self.client.post(reverse("account_logout"))

        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    def test_logout_with_deleted_organisation_returns_home(self):
        self.set_active_organisation(self.organisation.pk)
        self.organisation.delete()

        response = self.client.post(reverse("account_logout"))

        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
