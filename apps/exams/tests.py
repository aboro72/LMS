import json
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django_quill.quill import Quill

from apps.accounts.models import Rolle, UserProfile
from apps.organisations.models import Einladung, Organisation

from .models import Antwort, Frage, Fragenkatalog, FragenTag, Pruefung, PruefungsAnmeldung, PruefungsThemenquote, PruefungsVersuch, PruefungsbogenArchiv
from .forms import CSVImportForm
from .pdf import generiere_pruefungsbogen_pdf
from .services import NichtGenugFragenInThema, speichere_antwort, starte_pruefung, werte_versuch_aus


class ThemenquoteAuswahlTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="teilnehmer", password="testpass123")
        self.organisation = Organisation.objects.create(
            name="Testorganisation",
            slug="testorganisation",
            kontakt_email="test@example.com",
        )
        self.katalog = Fragenkatalog.objects.create(titel="Katalog", organisation=self.organisation)
        self.grundlagen = FragenTag.objects.create(name="Grundlagen", organisation=self.organisation)
        self.datenschutz = FragenTag.objects.create(name="Datenschutz", organisation=self.organisation)

    def frage(self, thema):
        frage = Frage.objects.create(
            fragenkatalog=self.katalog,
            typ=Frage.Typ.SINGLE_CHOICE,
            fragetext=Quill(json.dumps({"delta": "", "html": "<p>Beispielfrage</p>"})),
        )
        frage.tags.add(thema)
        return frage

    def test_zieht_die_vereinbarte_anzahl_pro_thema_ohne_doppelte_fragen(self):
        for _ in range(3):
            self.frage(self.grundlagen)
        for _ in range(3):
            self.frage(self.datenschutz)
        pruefung = Pruefung.objects.create(
            titel="Zertifikatsprüfung",
            organisation=self.organisation,
            fragenkatalog=self.katalog,
            anzahl_fragen=4,
        )
        PruefungsThemenquote.objects.create(pruefung=pruefung, thema=self.grundlagen, anzahl_fragen=2)
        PruefungsThemenquote.objects.create(pruefung=pruefung, thema=self.datenschutz, anzahl_fragen=2)

        versuch = starte_pruefung(pruefung, self.user)
        ausgewaehlt = Frage.objects.filter(id__in=versuch.fragen_reihenfolge)

        self.assertEqual(len(versuch.fragen_reihenfolge), 4)
        self.assertEqual(len(set(versuch.fragen_reihenfolge)), 4)
        self.assertEqual(ausgewaehlt.filter(tags=self.grundlagen).count(), 2)
        self.assertEqual(ausgewaehlt.filter(tags=self.datenschutz).count(), 2)

    def test_meldet_wenn_fuer_ein_thema_zu_wenige_fragen_vorhanden_sind(self):
        self.frage(self.grundlagen)
        pruefung = Pruefung.objects.create(
            titel="Zertifikatsprüfung",
            organisation=self.organisation,
            fragenkatalog=self.katalog,
            anzahl_fragen=2,
        )
        PruefungsThemenquote.objects.create(pruefung=pruefung, thema=self.grundlagen, anzahl_fragen=2)

        with self.assertRaises(NichtGenugFragenInThema):
            starte_pruefung(pruefung, self.user)

    def test_csv_import_ordnet_frage_dem_themengebiet_zu(self):
        datei = SimpleUploadedFile(
            "fragen.csv",
            "typ;fragetext;thema\nSC;Beispielfrage;Grundlagen, Datenschutz\n".encode("utf-8"),
            content_type="text/csv",
        )
        form = CSVImportForm(data={}, files={"datei": datei})

        self.assertTrue(form.is_valid())
        self.assertEqual(form.importiere(self.katalog), 1)
        frage = self.katalog.fragen.get()
        self.assertEqual(set(frage.tags.values_list("name", flat=True)), {"Grundlagen", "Datenschutz"})

    def test_csv_import_uebernimmt_altes_themenpraefix_und_entfernt_es_aus_der_frage(self):
        upload = SimpleUploadedFile(
            "fragen.csv",
            "typ;fragetext\nSC;[01 Grundlagen] Wofür steht die Abkürzung LAN?\n".encode("utf-8"),
            content_type="text/csv",
        )
        form = CSVImportForm(files={"datei": upload})
        self.assertTrue(form.is_valid())

        form.importiere(self.katalog)

        frage = Frage.objects.get(fragenkatalog=self.katalog)
        self.assertEqual(frage.fragetext.html, "Wofür steht die Abkürzung LAN?")
        self.assertEqual(list(frage.tags.values_list("name", flat=True)), ["Grundlagen"])

    def test_pruefungsbogen_pdf_enthaelt_pdf_signatur(self):
        frage = self.frage(self.grundlagen)
        pruefung = Pruefung.objects.create(
            titel="Druckprüfung",
            organisation=self.organisation,
            fragenkatalog=self.katalog,
            anzahl_fragen=1,
        )

        pdf = generiere_pruefungsbogen_pdf(pruefung, [frage], mit_loesungen=False)

        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_offline_bogen_archiviert_identische_teilnehmer_und_loesungsfassung(self):
        self.frage(self.grundlagen)
        pruefung = Pruefung.objects.create(
            titel="Offline-Pruefung", organisation=self.organisation,
            fragenkatalog=self.katalog, anzahl_fragen=1,
        )
        UserProfile.objects.create(nutzer=self.user, organisation=self.organisation, rolle=Rolle.EXAM_OPERATOR)
        self.client.force_login(self.user)
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post("/trainer/pruefungen/%s/offline-boegen/erstellen/" % pruefung.pk)
            self.assertEqual(response.status_code, 302)
            archiv = PruefungsbogenArchiv.objects.get(pruefung=pruefung)
            self.assertEqual(archiv.fragen_reihenfolge, [self.katalog.fragen.first().pk])
            self.assertTrue(archiv.teilnehmer_pdf.name.endswith("-teilnehmer.pdf"))
            self.assertTrue(archiv.loesung_pdf.name.endswith("-loesungen.pdf"))

    def test_einladung_meldet_lernenden_nach_annahme_zur_pruefung_an(self):
        pruefung = Pruefung.objects.create(
            titel="Einladungs-Pruefung", organisation=self.organisation,
            fragenkatalog=self.katalog, anzahl_fragen=1,
        )
        eingeladen = get_user_model().objects.create_user(
            username="eingeladen", email="neu@example.com", password="testpass123"
        )
        einladung = Einladung.objects.create(
            organisation=self.organisation, email="neu@example.com",
            rolle=Rolle.LEARNER, pruefung=pruefung, eingeladen_von=self.user,
        )
        self.client.force_login(eingeladen)
        response = self.client.get("/organisationen/einladung/%s/" % einladung.token)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PruefungsAnmeldung.objects.filter(nutzer=eingeladen, pruefung=pruefung).exists())

    def test_szenarioantwort_wird_gespeichert_und_zur_bewertung_vorgelegt(self):
        frage = Frage.objects.create(
            fragenkatalog=self.katalog,
            typ=Frage.Typ.SZENARIO,
            fragetext=Quill(json.dumps({"delta": "", "html": "<p>Analysieren Sie den Fehlerfall.</p>"})),
            punkte=5,
        )
        pruefung = Pruefung.objects.create(titel="Szenario", organisation=self.organisation, fragenkatalog=self.katalog, anzahl_fragen=1)
        versuch = starte_pruefung(pruefung, self.user)

        antwort = speichere_antwort(versuch, frage, {"freitext_antwort": "AAAA steht für IPv6; A ist für IPv4."})
        werte_versuch_aus(versuch)

        versuch.refresh_from_db()
        self.assertEqual(antwort.freitext_antwort, "AAAA steht für IPv6; A ist für IPv4.")
        self.assertEqual(versuch.status, PruefungsVersuch.Status.AUSSTEHEND)

    @override_settings(FIELD_ENCRYPTION_KEY="j3BQv31KKjfteqM5y4LTfhQf3ru51qCz_02cxydQaDI=")
    def test_ergebnis_wird_verschluesselt_und_ein_jahr_vorgehalten(self):
        frage = self.frage(self.grundlagen)
        antwort = Antwort.objects.create(frage=frage, antworttext="Richtig", ist_korrekt=True)
        pruefung = Pruefung.objects.create(
            titel="Ergebnisprüfung",
            organisation=self.organisation,
            fragenkatalog=self.katalog,
            anzahl_fragen=1,
        )
        versuch = starte_pruefung(pruefung, self.user)
        speichere_antwort(versuch, frage, {"antworten": [str(antwort.id)]})
        werte_versuch_aus(versuch)
        with connection.cursor() as cursor:
            cursor.execute("SELECT ergebnis_verschluesselt FROM exams_pruefungsversuch WHERE id = %s", [versuch.pk])
            verschluesselt = cursor.fetchone()[0]

        self.assertTrue(verschluesselt.startswith("enc:v1:"))
        self.assertIsNotNone(versuch.einsehbar_bis)
        self.assertEqual((versuch.einsehbar_bis - versuch.abgeschlossen_am).days, 365)

    def test_loeschen_des_katalogs_entfernt_abhaengige_fragen_und_pruefungen(self):
        frage = self.frage(self.grundlagen)
        Antwort.objects.create(frage=frage, antworttext="Richtig", ist_korrekt=True)
        pruefung = Pruefung.objects.create(
            titel="Zu löschende Prüfung",
            organisation=self.organisation,
            fragenkatalog=self.katalog,
            anzahl_fragen=1,
        )
        katalog_id = self.katalog.pk

        self.katalog.delete()

        self.assertFalse(Fragenkatalog.objects.filter(pk=katalog_id).exists())
        self.assertFalse(Frage.objects.filter(pk=frage.pk).exists())
        self.assertFalse(Antwort.objects.filter(frage=frage).exists())
        self.assertFalse(Pruefung.objects.filter(pk=pruefung.pk).exists())
        self.assertTrue(FragenTag.objects.filter(pk=self.grundlagen.pk).exists())
