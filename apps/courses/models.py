from django.conf import settings
from django.db import models
from django_quill.fields import QuillField


class Niveau(models.TextChoices):
    ANFAENGER = "anfaenger", "Anfaenger"
    MITTEL = "mittel", "Mittel"
    FORTGESCHRITTEN = "fortgeschritten", "Fortgeschritten"


class Kurs(models.Model):
    titel = models.CharField(max_length=300)
    slug = models.SlugField(unique=True)
    beschreibung = QuillField()
    thumbnail = models.ImageField(upload_to="thumbnails/", blank=True)
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE)
    erstellt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    sprache = models.CharField(max_length=10, default="de")
    niveau = models.CharField(max_length=20, choices=Niveau.choices)
    ist_veroeffentlicht = models.BooleanField(default=False)
    ist_kostenlos = models.BooleanField(default=True)
    preis = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    pruefung = models.ForeignKey(
        "exams.Pruefung",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kurse",
    )
    erstellt_am = models.DateTimeField(auto_now_add=True)
    geaendert_am = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["titel"]
        verbose_name = "Kurs"
        verbose_name_plural = "Kurse"

    def __str__(self):
        return self.titel

    @property
    def dauer_minuten(self):
        return sum(lektion.dauer_minuten for abschnitt in self.abschnitte.all() for lektion in abschnitt.lektionen.all())


class Abschnitt(models.Model):
    kurs = models.ForeignKey(Kurs, on_delete=models.CASCADE, related_name="abschnitte")
    titel = models.CharField(max_length=200)
    reihenfolge = models.PositiveIntegerField(default=0)
    ist_veroeffentlicht = models.BooleanField(default=True)

    class Meta:
        ordering = ["reihenfolge"]
        verbose_name = "Abschnitt"
        verbose_name_plural = "Abschnitte"

    def __str__(self):
        return f"{self.kurs}: {self.titel}"


class Lektion(models.Model):
    class Typ(models.TextChoices):
        VIDEO = "VIDEO", "Video"
        DOKUMENT = "DOKUMENT", "Dokument"
        TEXT = "TEXT", "Text/HTML"
        QUIZ = "QUIZ", "Mini-Quiz"

    abschnitt = models.ForeignKey(Abschnitt, on_delete=models.CASCADE, related_name="lektionen")
    titel = models.CharField(max_length=200)
    typ = models.CharField(max_length=20, choices=Typ.choices)
    reihenfolge = models.PositiveIntegerField(default=0)
    inhalt = QuillField(blank=True)
    video_url = models.URLField(blank=True)
    datei = models.FileField(upload_to="lektionen/", blank=True)
    dauer_minuten = models.PositiveIntegerField(default=0)
    ist_vorschau = models.BooleanField(default=False)

    class Meta:
        ordering = ["reihenfolge"]
        verbose_name = "Lektion"
        verbose_name_plural = "Lektionen"

    def __str__(self):
        return f"{self.abschnitt}: {self.titel}"


class Einschreibung(models.Model):
    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kurs = models.ForeignKey(Kurs, on_delete=models.CASCADE)
    eingeschrieben_am = models.DateTimeField(auto_now_add=True)
    abgeschlossen_am = models.DateTimeField(null=True, blank=True)
    fortschritt_prozent = models.PositiveIntegerField(default=0)
    bezahlt = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["nutzer", "kurs"], name="unique_user_course_enrollment")
        ]
        verbose_name = "Einschreibung"
        verbose_name_plural = "Einschreibungen"

    def __str__(self):
        return f"{self.nutzer} - {self.kurs}"

    def aktualisiere_fortschritt(self):
        lektionen_gesamt = Lektion.objects.filter(abschnitt__kurs=self.kurs).count()
        if lektionen_gesamt == 0:
            self.fortschritt_prozent = 0
        else:
            abgeschlossen = self.lektionsfortschritt_set.count()
            self.fortschritt_prozent = round((abgeschlossen / lektionen_gesamt) * 100)
        self.save(update_fields=["fortschritt_prozent"])


class LektionsFortschritt(models.Model):
    einschreibung = models.ForeignKey(Einschreibung, on_delete=models.CASCADE)
    lektion = models.ForeignKey(Lektion, on_delete=models.CASCADE)
    abgeschlossen_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["einschreibung", "lektion"], name="unique_lesson_progress")
        ]
        verbose_name = "Lektionsfortschritt"
        verbose_name_plural = "Lektionsfortschritte"

    def __str__(self):
        return f"{self.einschreibung} - {self.lektion}"
