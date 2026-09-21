from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class InitialSuperadminTests(TestCase):
    def test_creates_superadmin_and_preserves_changed_password_on_rerun(self):
        call_command("create_initial_superadmin", stdout=StringIO())
        user = get_user_model().objects.get(username="superadmin")
        self.assertTrue(user.is_active and user.is_staff and user.is_superuser)
        self.assertTrue(user.check_password("Passw0rt123!"))
        self.assertTrue(user.groups.filter(name="superadmin").exists())
        user.set_password("Changed-password-456!")
        user.save()

        call_command("create_initial_superadmin", stdout=StringIO())
        user.refresh_from_db()
        self.assertTrue(user.check_password("Changed-password-456!"))
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_existing_regular_user_is_not_promoted_or_reset(self):
        user = get_user_model().objects.create_user(
            username="superadmin", password="Existing-password-456!"
        )
        with self.assertRaises(CommandError):
            call_command("create_initial_superadmin", stdout=StringIO())
        user.refresh_from_db()
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password("Existing-password-456!"))
