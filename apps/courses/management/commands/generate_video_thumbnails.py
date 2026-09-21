from django.core.management.base import BaseCommand

from apps.courses.models import Lektion
from apps.courses.video_thumbnails import generate_lesson_video_thumbnail


class Command(BaseCommand):
    help = "Generate thumbnails for uploaded lesson videos."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Regenerate existing thumbnails.")

    def handle(self, *args, **options):
        queryset = Lektion.objects.filter(typ=Lektion.Typ.VIDEO).exclude(datei="")
        created = 0
        skipped = 0
        failed = 0
        for lektion in queryset.iterator():
            if lektion.video_thumbnail and not options["force"]:
                skipped += 1
                continue
            if generate_lesson_video_thumbnail(lektion):
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Thumbnail erzeugt: {lektion.pk} {lektion.titel}"))
            else:
                failed += 1
                self.stdout.write(self.style.WARNING(f"Kein Thumbnail erzeugt: {lektion.pk} {lektion.titel}"))
        self.stdout.write(f"Fertig. erzeugt={created}, uebersprungen={skipped}, fehlgeschlagen={failed}")
