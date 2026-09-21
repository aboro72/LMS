from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Rolle


class Command(BaseCommand):
    help = "Erstellt den initialen SuperAdmin, ohne bestehende Konten zu veraendern."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        existing = User.objects.filter(username="superadmin").first()
        if existing is not None:
            if not (existing.is_superuser and existing.is_staff and existing.is_active):
                raise CommandError(
                    "Das Konto 'superadmin' existiert bereits, ist aber kein aktiver "
                    "SuperAdmin. Bitte das Konto manuell pruefen."
                )
            self.stdout.write("SuperAdmin 'superadmin' existiert bereits. Passwort bleibt unveraendert.")
            return

        user = User.objects.create_superuser(
            username="superadmin", email="", password="Passw0rt123!"
        )
        group, _ = Group.objects.get_or_create(name=Rolle.SUPERADMIN)
        user.groups.add(group)
        self.stdout.write(self.style.SUCCESS("SuperAdmin erstellt: superadmin"))
        self.stdout.write("Initialpasswort: Passw0rt123! Bitte nach der Anmeldung aendern.")
