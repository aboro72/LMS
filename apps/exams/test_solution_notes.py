from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from reportlab.platypus import Paragraph

from apps.accounts.management.commands.create_demo_data import Command, PRUEFUNGSFRAGEN, quill_html
from apps.organisations.models import Organisation

from .models import Frage, Fragenkatalog, Pruefung
from .pdf import generiere_pruefungsbogen_pdf


class SolutionNotesTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Demo", slug="demo-organisation")
        self.catalog = Fragenkatalog.objects.create(
            titel="ABoroLMS Zertifikatsfragen", organisation=self.org,
        )

    def test_explanations_in_solution_only_for_every_question_type(self):
        exam = Pruefung(titel="Test & Bewertung", bestehensgrenze_prozent=70)
        for question_type in Frage.Typ:
            with self.subTest(question_type=question_type):
                question = Frage.objects.create(
                    fragenkatalog=self.catalog, typ=question_type,
                    fragetext=quill_html("<p>Welche Antwort?</p>"), punkte=3,
                    erklaerung=quill_html("<p>Erwartet: A &amp; B &lt; C.</p><p>Auch sinngemaess korrekt.</p>"),
                    bewertungshinweis=quill_html("<p>Kriterium eins: 1 Punkt.</p><p>Kriterium zwei: 2 Punkte.</p>"),
                )
                for solutions in (True, False):
                    with patch("apps.exams.pdf.Paragraph", wraps=Paragraph) as paragraphs:
                        pdf = generiere_pruefungsbogen_pdf(exam, [question], mit_loesungen=solutions)
                    self.assertTrue(pdf.startswith(b"%PDF"))
                    content = "\n".join(call.args[0] for call in paragraphs.call_args_list)
                    self.assertEqual("Erwartet:" in content, solutions)
                    manual = question_type in (Frage.Typ.FREITEXT, Frage.Typ.SZENARIO)
                    self.assertEqual("Kriterium eins" in content, solutions and manual)
                    if solutions:
                        self.assertIn("A &amp; B &lt; C.<br/>Auch sinngemaess korrekt.", content)

    def test_demo_questions_are_created_with_explanations_and_manual_rubric(self):
        Command()._setup_pruefungsfragen(self.catalog)
        self.assertEqual(self.catalog.fragen.count(), len(PRUEFUNGSFRAGEN))
        for question in self.catalog.fragen.all():
            self.assertTrue(question.erklaerung.html)
            if question.typ == Frage.Typ.FREITEXT:
                self.assertIn("Maximal 3 Punkte", question.bewertungshinweis.html)

    def test_backfill_preserves_questions_answers_and_existing_notes(self):
        Command()._setup_pruefungsfragen(self.catalog)
        ids = list(self.catalog.fragen.values_list("pk", flat=True))
        answers = list(self.catalog.fragen.first().antworten.values_list("pk", flat=True))
        for question in self.catalog.fragen.all():
            question.erklaerung = quill_html("")
            question.bewertungshinweis = quill_html("")
            question.save(update_fields=["erklaerung", "bewertungshinweis"])
        custom = self.catalog.fragen.first()
        custom.erklaerung = quill_html("<p>Eigene Erklaerung.</p>")
        custom.save(update_fields=["erklaerung"])
        other_org = Organisation.objects.create(name="Andere", slug="andere")
        other_catalog = Fragenkatalog.objects.create(titel=self.catalog.titel, organisation=other_org)
        other = Frage.objects.create(
            fragenkatalog=other_catalog, typ=custom.typ, fragetext=custom.fragetext,
        )
        unknown = Frage.objects.create(
            fragenkatalog=self.catalog, typ=Frage.Typ.FREITEXT,
            fragetext=quill_html("<p>Individuelle Frage.</p>"),
        )

        call_command("ergaenze_zertifikatsfragen", stdout=StringIO())

        self.assertEqual(list(self.catalog.fragen.exclude(pk=unknown.pk).values_list("pk", flat=True)), ids)
        self.assertEqual(list(custom.antworten.values_list("pk", flat=True)), answers)
        custom.refresh_from_db()
        self.assertEqual(custom.erklaerung.html, "<p>Eigene Erklaerung.</p>")
        other.refresh_from_db()
        unknown.refresh_from_db()
        self.assertFalse(other.erklaerung.html)
        self.assertFalse(unknown.erklaerung.html)
        for question in self.catalog.fragen.exclude(pk=unknown.pk):
            self.assertTrue(question.erklaerung.html)
        manual = self.catalog.fragen.get(typ=Frage.Typ.FREITEXT, pk__in=ids)
        self.assertIn("Maximal 3 Punkte", manual.bewertungshinweis.html)
        output = StringIO()
        call_command("ergaenze_zertifikatsfragen", stdout=output)
        self.assertIn("0 Fragen ergaenzt", output.getvalue())
