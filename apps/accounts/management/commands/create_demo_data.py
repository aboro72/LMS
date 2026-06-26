from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django_quill.quill import Quill

from apps.accounts.models import Rolle, UserProfile
from apps.courses.models import Abschnitt, Begleitmaterial, Kurs, Lektion, Niveau, Uebungsantwort, Uebungsfrage
from apps.exams.models import Antwort, Frage, Fragenkatalog, Pruefung
from apps.organisations.models import LizenzTyp, Organisation
from apps.payments.models import Zahlung, Zahlungseinstellungen, Zahlungsart
from apps.payments.services import bestaetige_zahlung, erstelle_zahlung


def quill_html(html):
    return Quill('{"delta": "", "html": ' + __import__("json").dumps(html) + "}")


class Command(BaseCommand):
    help = "Erstellt eine Demo-Organisation mit Beispielnutzern und Rollen."

    def handle(self, *args, **options):
        for role in Rolle:
            Group.objects.get_or_create(name=role.value)

        user_model = get_user_model()
        superadmin, _ = user_model.objects.get_or_create(
            username="superadmin",
            defaults={
                "email": "superadmin@example.com",
                "first_name": "Super",
                "last_name": "Admin",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        superadmin.is_staff = True
        superadmin.is_superuser = True
        superadmin.set_password("ChangeMe123!")
        superadmin.save()
        superadmin.groups.add(Group.objects.get(name=Rolle.SUPERADMIN.value))

        organisation, _ = Organisation.objects.get_or_create(
            slug="demo-organisation",
            defaults={
                "name": "Demo Organisation",
                "kontakt_email": "demo@aborosoft.de",
                "lizenz_typ": LizenzTyp.PRO,
                "max_nutzer": 100,
                "max_kurse": 25,
            },
        )
        payment_settings = Zahlungseinstellungen.load()
        payment_settings.stripe_aktiv = True
        payment_settings.google_pay_aktiv = True
        payment_settings.paypal_aktiv = True
        payment_settings.ueberweisung_aktiv = True
        payment_settings.demo_autoconfirm = True
        payment_settings.kontoinhaber = "ABoroSoft"
        payment_settings.iban = "DE02120300000000202051"
        payment_settings.bic = "BYLADEM1001"
        payment_settings.bankname = "Demo Bank"
        payment_settings.save()

        demo_users = [
            ("orgadmin", Rolle.ORG_ADMIN),
            ("trainer", Rolle.TRAINER),
            ("examiner", Rolle.EXAMINER),
            ("learner", Rolle.LEARNER),
        ]
        for username, role in demo_users:
            user, created = user_model.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.com",
                    "first_name": username.title(),
                },
            )
            user.set_password("ChangeMe123!")
            user.save(update_fields=["password"])
            group = Group.objects.get(name=role.value)
            user.groups.add(group)
            UserProfile.objects.get_or_create(
                nutzer=user,
                organisation=organisation,
                rolle=role,
            )

        trainer = user_model.objects.get(username="trainer")
        kurs, _ = Kurs.objects.get_or_create(
            slug="aborolms-grundlagen",
            defaults={
                "titel": "ABoroLMS Grundlagen",
                "beschreibung": quill_html(
                    "<p>Ein kompakter Demo-Kurs zur Vorbereitung auf die ABoroLMS Grundlagen Zertifikatspruefung.</p>"
                ),
                "organisation": organisation,
                "erstellt_von": trainer,
                "sprache": "de",
                "niveau": Niveau.ANFAENGER,
                "ist_veroeffentlicht": True,
                "ist_kostenlos": True,
            },
        )
        kurs.beschreibung = quill_html(
            "<p>Ein kompakter Demo-Kurs zur Vorbereitung auf die ABoroLMS Grundlagen Zertifikatspruefung.</p>"
        )
        kurs.ist_veroeffentlicht = True
        kurs.ist_kostenlos = False
        kurs.preis = 49
        kurs.save(update_fields=["beschreibung", "ist_veroeffentlicht", "ist_kostenlos", "preis"])

        kursinhalte = [
            (
                "Grundlagen der Plattform",
                [
                    (
                        "Was ABoroLMS leisten soll",
                        6,
                        "<h2>Was ABoroLMS leisten soll</h2>"
                        "<p>ABoroLMS ist eine Lernplattform fuer strukturierte Kurse, Pruefungen und spaeter Zertifikate. "
                        "Der Demo-Kurs zeigt den Grundfluss: Kurs ansehen, Lektionen bearbeiten, Fortschritt speichern und eine Abschlusspruefung starten.</p>"
                        "<p>Wichtig fuer die Pruefung: ABoroLMS trennt Lerninhalte, Pruefungsversuche und spaeter Zertifikate sauber voneinander.</p>",
                        True,
                        Lektion.Typ.VIDEO,
                    ),
                    (
                        "Mandantenfaehigkeit verstehen",
                        8,
                        "<h2>Mandantenfaehigkeit verstehen</h2>"
                        "<p>Mandantenfaehigkeit bedeutet, dass mehrere Organisationen dieselbe Installation nutzen koennen, ihre Daten aber logisch getrennt bleiben. "
                        "Eine Organisation sieht ihre eigenen Kurse, Nutzer, Fragenkataloge und Pruefungen.</p>"
                        "<p>Falsch waere: Alle Nutzer teilen automatisch dieselben Kurse oder jede Organisation braucht zwingend eine eigene Python-Installation. "
                        "Richtig ist die Datenisolierung ueber Organisationsbezug und gefilterte QuerySets.</p>",
                        False,
                        Lektion.Typ.TEXT,
                    ),
                ],
            ),
            (
                "Rollen und Verantwortlichkeiten",
                [
                    (
                        "Die fuenf Demo-Rollen",
                        7,
                        "<h2>Die fuenf Demo-Rollen</h2>"
                        "<ul>"
                        "<li><strong>Super-Admin:</strong> betreibt die Plattform und kann alles verwalten.</li>"
                        "<li><strong>Org-Admin:</strong> verwaltet Nutzer und Einstellungen der eigenen Organisation.</li>"
                        "<li><strong>Trainer:</strong> erstellt und pflegt Kurse, Fragenkataloge und Pruefungen.</li>"
                        "<li><strong>Pruefer:</strong> bewertet manuelle Freitextantworten.</li>"
                        "<li><strong>Lernender:</strong> nimmt an Kursen teil und absolviert Pruefungen.</li>"
                        "</ul>"
                        "<p>Ein Nutzer kann mehrere Rollen gleichzeitig haben, zum Beispiel Trainer und Lernender.</p>",
                        False,
                        Lektion.Typ.TEXT,
                    ),
                    (
                        "Rollen technisch abbilden",
                        6,
                        "<h2>Rollen technisch abbilden</h2>"
                        "<p>ABoroLMS nutzt Django Groups fuer Rollennamen und ein UserProfile fuer die Zuordnung Nutzer, Organisation und Rolle. "
                        "Dadurch kann derselbe Nutzer in einer Organisation Trainer sein und in einer anderen nur Lernender.</p>"
                        "<p>Fuer die Pruefung merken: Rollen ersetzen keine Mandantenfilter. Views muessen trotzdem nach Organisation filtern.</p>",
                        False,
                        Lektion.Typ.TEXT,
                    ),
                ],
            ),
            (
                "Kurse, Lektionen und Fortschritt",
                [
                    (
                        "Aufbau eines Kurses",
                        8,
                        "<h2>Aufbau eines Kurses</h2>"
                        "<p>Ein Kurs besteht aus Abschnitten und Lektionen. Abschnitte gruppieren Inhalte, Lektionen enthalten Text, Videos, Dokumente oder spaeter Mini-Quizze. "
                        "Die Reihenfolge wird gespeichert, damit Lernende einen klaren Lernpfad haben.</p>"
                        "<p>Ein professioneller Kursbereich braucht daher mindestens Kursdaten, strukturierte Lektionen und eine verstaendliche Navigation.</p>",
                        False,
                        Lektion.Typ.TEXT,
                    ),
                    (
                        "Fortschritt speichern",
                        7,
                        "<h2>Fortschritt speichern</h2>"
                        "<p>Wenn eine Lektion als abgeschlossen markiert wird, erstellt ABoroLMS einen LektionsFortschritt fuer die Einschreibung. "
                        "Danach wird der Fortschritt in Prozent neu berechnet.</p>"
                        "<p>Wichtig: Der Abschluss einer Lektion loescht nichts und veraendert keine Rollen. Er dokumentiert nur den Lernstand dieses Nutzers in diesem Kurs.</p>",
                        False,
                        Lektion.Typ.TEXT,
                    ),
                ],
            ),
            (
                "Pruefung und Zertifikatslogik",
                [
                    (
                        "Warum Pruefungsversuche gespeichert werden",
                        8,
                        "<h2>Warum Pruefungsversuche gespeichert werden</h2>"
                        "<p>Jede gestartete Pruefung erzeugt einen PruefungsVersuch. Darin stehen Versuchnummer, Startzeit, Status, ausgewaehlte Fragen, Punkte und Ergebnis. "
                        "So bleibt nachvollziehbar, wann ein Nutzer welche Pruefung absolviert hat.</p>"
                        "<p>Die Fragen bleiben im Katalog erhalten. Antworten des Teilnehmers werden separat am Versuch gespeichert.</p>",
                        False,
                        Lektion.Typ.TEXT,
                    ),
                    (
                        "Bestehensgrenze und Zufall",
                        6,
                        "<h2>Bestehensgrenze und Zufall</h2>"
                        "<p>Die Bestehensgrenze legt fest, ab welchem Prozentwert ein Versuch bestanden ist. In der Demo-Pruefung liegt sie bei 70 Prozent. "
                        "Fragen und Antworten koennen zufaellig sortiert werden, damit nicht jeder Versuch gleich aussieht.</p>"
                        "<p>Falsch waere: Eine falsche Antwort erzeugt automatisch ein Zertifikat oder ein Zeitlimit loescht Daten. "
                        "Richtig ist: Bewertet wird anhand erreichter Punkte und der konfigurierten Bestehensgrenze.</p>",
                        False,
                        Lektion.Typ.TEXT,
                    ),
                ],
            ),
        ]
        for abschnitt_position, (abschnitt_titel, lektionen) in enumerate(kursinhalte, start=1):
            abschnitt, _ = Abschnitt.objects.get_or_create(
                kurs=kurs,
                reihenfolge=abschnitt_position,
                defaults={"titel": abschnitt_titel},
            )
            if abschnitt.titel != abschnitt_titel:
                abschnitt.titel = abschnitt_titel
                abschnitt.save(update_fields=["titel"])
            for lektion_position, (titel, dauer, html, ist_vorschau, typ) in enumerate(lektionen, start=1):
                lektion, _ = Lektion.objects.get_or_create(
                    abschnitt=abschnitt,
                    reihenfolge=lektion_position,
                    defaults={
                        "titel": titel,
                        "typ": typ,
                        "inhalt": quill_html(html),
                        "dauer_minuten": dauer,
                        "ist_vorschau": ist_vorschau,
                    },
                )
                lektion.titel = titel
                lektion.typ = typ
                lektion.inhalt = quill_html(html)
                lektion.dauer_minuten = dauer
                lektion.ist_vorschau = ist_vorschau
                lektion.save(update_fields=["titel", "typ", "inhalt", "dauer_minuten", "ist_vorschau"])

        uebungen = {
            "Was ABoroLMS leisten soll": (
                "Welche Aussage beschreibt den Demo-Kurs am besten?",
                [
                    ("Er zeigt Kurs, Lernfortschritt und Abschlusspruefung im Zusammenspiel.", True),
                    ("Er ist nur eine statische Startseite ohne Lernlogik.", False),
                    ("Er ersetzt die Benutzerrollen durch zufaellige Kursnamen.", False),
                ],
                "Der Kurs verbindet Lektionen, Fortschritt und Pruefung zu einem durchgehenden Lernfluss.",
            ),
            "Mandantenfaehigkeit verstehen": (
                "Was bedeutet Mandantenfaehigkeit in ABoroLMS?",
                [
                    ("Organisationen nutzen dieselbe Installation, ihre Daten bleiben logisch getrennt.", True),
                    ("Alle Organisationen muessen dieselben Nutzer und Kurse teilen.", False),
                    ("Jede Organisation braucht zwingend eine eigene Datenbanktabelle pro Lektion.", False),
                ],
                "Mandantenfaehigkeit meint Datenisolation nach Organisation.",
            ),
            "Die fuenf Demo-Rollen": (
                "Welche Rolle erstellt Kurse und Fragenkataloge?",
                [
                    ("Trainer", True),
                    ("Lernender", False),
                    ("Anonymer Besucher", False),
                ],
                "Trainer pflegen Kurse, Lektionen, Fragenkataloge und Pruefungen.",
            ),
            "Rollen technisch abbilden": (
                "Welche Bausteine bilden Rollen und Organisationen ab?",
                [
                    ("Django Groups und UserProfile", True),
                    ("Nur Browser-Cookies ohne Datenbankbezug", False),
                    ("Ausschliesslich Dateinamen im Medienordner", False),
                ],
                "Groups liefern Rollennamen, UserProfile verknuepft Nutzer, Organisation und Rolle.",
            ),
            "Aufbau eines Kurses": (
                "Woraus besteht ein strukturierter ABoroLMS-Kurs?",
                [
                    ("Aus Abschnitten und Lektionen in Reihenfolge.", True),
                    ("Nur aus einer einzigen globalen Textdatei.", False),
                    ("Aus Zertifikaten ohne Lerninhalte.", False),
                ],
                "Abschnitte gruppieren Lektionen und bilden den Lernpfad.",
            ),
            "Fortschritt speichern": (
                "Was passiert beim Abschliessen einer Lektion?",
                [
                    ("Ein Lektionsfortschritt wird gespeichert und der Prozentwert aktualisiert.", True),
                    ("Der Nutzer wird automatisch Super-Admin.", False),
                    ("Die Lektion wird fuer alle geloescht.", False),
                ],
                "Der Fortschritt gehoert zur Einschreibung des Lernenden.",
            ),
            "Warum Pruefungsversuche gespeichert werden": (
                "Warum wird ein PruefungsVersuch angelegt?",
                [
                    ("Damit Startzeit, Antworten, Punkte und Ergebnis nachvollziehbar bleiben.", True),
                    ("Damit Fragen aus dem Katalog verschwinden.", False),
                    ("Damit jede Antwort einen neuen Kurs erzeugt.", False),
                ],
                "Der Versuch dokumentiert einen konkreten Pruefungslauf.",
            ),
            "Bestehensgrenze und Zufall": (
                "Welche Aussage zur Bestehensgrenze ist richtig?",
                [
                    ("Sie legt den Prozentwert fest, ab dem bestanden ist.", True),
                    ("Sie loescht nach Ablauf automatisch die Datenbank.", False),
                    ("Sie ersetzt alle richtigen Antworten durch Zufallstexte.", False),
                ],
                "In der Demo-Pruefung gilt eine Bestehensgrenze von 70 Prozent.",
            ),
        }
        for titel, (frage_text, antworten, erklaerung) in uebungen.items():
            lektion = Lektion.objects.get(abschnitt__kurs=kurs, titel=titel)
            frage, _ = Uebungsfrage.objects.get_or_create(
                lektion=lektion,
                frage=frage_text,
                defaults={
                    "erklaerung": erklaerung,
                    "reihenfolge": 1,
                    "aktiv": True,
                },
            )
            frage.erklaerung = erklaerung
            frage.aktiv = True
            frage.save(update_fields=["erklaerung", "aktiv"])
            if not frage.antworten.exists():
                for antwort_position, (antwort_text, ist_korrekt) in enumerate(antworten, start=1):
                    Uebungsantwort.objects.create(
                        frage=frage,
                        antwort=antwort_text,
                        ist_korrekt=ist_korrekt,
                        reihenfolge=antwort_position,
                    )

        materialien = {
            "Mandantenfaehigkeit verstehen": (
                "Merkblatt Mandantenfaehigkeit.txt",
                "Merksatz: Eine Selfhosting-Installation kann mehrere Organisationen bedienen. QuerySets und Profile sorgen fuer Datenisolation.\n",
            ),
            "Bestehensgrenze und Zufall": (
                "Pruefungsvorbereitung.txt",
                "Vor der Zertifikatspruefung wiederholen: Rollen, Mandantenfaehigkeit, Kursstruktur, Fortschritt und Pruefungsversuche.\n",
            ),
        }
        for lektion_titel, (dateiname, inhalt) in materialien.items():
            lektion = Lektion.objects.get(abschnitt__kurs=kurs, titel=lektion_titel)
            material, created = Begleitmaterial.objects.get_or_create(
                lektion=lektion,
                titel=dateiname.replace(".txt", ""),
                defaults={"reihenfolge": 1},
            )
            if created or not material.datei:
                material.datei.save(dateiname, ContentFile(inhalt.encode("utf-8")), save=True)

        katalog, _ = Fragenkatalog.objects.get_or_create(
            titel="ABoroLMS Zertifikatsfragen",
            organisation=organisation,
            defaults={
                "beschreibung": "Demo-Fragenkatalog fuer die ABoroLMS-Grundlagenzertifizierung.",
                "erstellt_von": trainer,
            },
        )
        pruefung, _ = Pruefung.objects.get_or_create(
            titel="ABoroLMS Grundlagen Zertifikatspruefung",
            organisation=organisation,
            defaults={
                "beschreibung": "Bestehe diese Demo-Pruefung, um in Phase 4 ein Zertifikat zu erzeugen.",
                "fragenkatalog": katalog,
                "anzahl_fragen": 8,
                "zeitlimit_minuten": 20,
                "bestehensgrenze_prozent": 70,
                "max_versuche": None,
                "zufaellige_fragenreihenfolge": True,
                "zufaellige_antwortfolge": True,
                "ist_aktiv": True,
            },
        )
        if kurs.pruefung_id != pruefung.id:
            kurs.pruefung = pruefung
            kurs.save(update_fields=["pruefung"])

        learner = user_model.objects.get(username="learner")
        if not Zahlung.objects.filter(nutzer=learner, kurs=kurs, status="bezahlt").exists():
            zahlung = erstelle_zahlung(kurs, learner, Zahlungsart.STRIPE)
            bestaetige_zahlung(zahlung, provider_referenz="demo-paid-course-access")

        fragen = [
            {
                "typ": Frage.Typ.SINGLE_CHOICE,
                "text": "Was ist der wichtigste Zweck einer mandantenfaehigen Lernplattform?",
                "punkte": 2,
                "antworten": [
                    ("Daten verschiedener Organisationen bleiben logisch getrennt.", True),
                    ("Alle Nutzer teilen sich automatisch dieselben Kurse und Zertifikate.", False),
                    ("Jede Organisation bekommt zwingend eine eigene Python-Installation.", False),
                    ("Mandantenfaehigkeit bedeutet, dass nur Super-Admins Kurse sehen koennen.", False),
                ],
            },
            {
                "typ": Frage.Typ.MULTIPLE_CHOICE,
                "text": "Welche Aussagen passen zum Rollenmodell von ABoroLMS?",
                "punkte": 2,
                "antworten": [
                    ("Ein Nutzer kann mehrere Rollen gleichzeitig haben.", True),
                    ("Rollen werden ueber Django Groups und UserProfile abgebildet.", True),
                    ("Ein Trainer darf automatisch Daten fremder Organisationen bearbeiten.", False),
                    ("Ein Lernender ist immer auch Pruefer, sobald er eingeschrieben ist.", False),
                ],
            },
            {
                "typ": Frage.Typ.SINGLE_CHOICE,
                "text": "Welche Rolle erstellt und pflegt Kurse innerhalb ihrer Organisation?",
                "punkte": 1,
                "antworten": [
                    ("Trainer", True),
                    ("Lernender", False),
                    ("Pruefer", False),
                    ("AnonymousUser", False),
                ],
            },
            {
                "typ": Frage.Typ.MULTIPLE_CHOICE,
                "text": "Welche Funktionen gehoeren zu einem professionellen Kursbereich?",
                "punkte": 2,
                "antworten": [
                    ("Abschnitte und Lektionen in definierter Reihenfolge.", True),
                    ("Fortschrittsverfolgung je Einschreibung.", True),
                    ("Zufaellige Loeschung alter Lektionen bei jedem Login.", False),
                    ("Bewertungssterne als Ersatz fuer saubere Kursinhalte.", False),
                ],
            },
            {
                "typ": Frage.Typ.SINGLE_CHOICE,
                "text": "Was passiert beim erfolgreichen Markieren einer Lektion als abgeschlossen?",
                "punkte": 1,
                "antworten": [
                    ("Ein Lektionsfortschritt wird gespeichert und der Kursfortschritt aktualisiert.", True),
                    ("Der Kurs wird sofort geloescht, damit keine Dopplung entsteht.", False),
                    ("Der Nutzer verliert seine Rolle als Lernender.", False),
                    ("Die Lektion wird fuer alle Organisationen veroeffentlicht.", False),
                ],
            },
            {
                "typ": Frage.Typ.WAHR_FALSCH,
                "text": "Ein Org-Admin oder Trainer soll nur Daten seiner eigenen Organisation sehen.",
                "punkte": 1,
                "antworten": [
                    ("Wahr", True),
                    ("Falsch", False),
                ],
            },
            {
                "typ": Frage.Typ.SINGLE_CHOICE,
                "text": "Warum werden Pruefungsversuche separat gespeichert?",
                "punkte": 2,
                "antworten": [
                    ("Damit Startzeit, Status, Antworten, Punkte und Ergebnis nachvollziehbar bleiben.", True),
                    ("Damit jeder Seitenaufruf eine neue Organisation erzeugt.", False),
                    ("Damit Fragen nach jeder Antwort dauerhaft aus dem Katalog verschwinden.", False),
                    ("Damit Zertifikate ohne Nutzerbezug ausgestellt werden muessen.", False),
                ],
            },
            {
                "typ": Frage.Typ.MULTIPLE_CHOICE,
                "text": "Welche Aussagen zur Zertifikatspruefung sind korrekt?",
                "punkte": 2,
                "antworten": [
                    ("Eine Bestehensgrenze legt fest, ab welchem Prozentwert bestanden ist.", True),
                    ("Fragen und Antworten koennen zufaellig sortiert werden.", True),
                    ("Jede falsche Antwort erzeugt automatisch ein gueltiges Zertifikat.", False),
                    ("Ein Zeitlimit bedeutet, dass die Datenbank nach Ablauf geloescht wird.", False),
                ],
            },
        ]
        for position, daten in enumerate(fragen, start=1):
            frage, created = Frage.objects.get_or_create(
                fragenkatalog=katalog,
                fragetext=quill_html("<p>" + daten["text"] + "</p>"),
                defaults={
                    "typ": daten["typ"],
                    "punkte": daten["punkte"],
                    "schwierigkeit": Frage.Schwierigkeit.MITTEL,
                },
            )
            if not created:
                continue
            for antwort_position, (antworttext, ist_korrekt) in enumerate(daten["antworten"], start=1):
                Antwort.objects.create(
                    frage=frage,
                    antworttext=antworttext,
                    ist_korrekt=ist_korrekt,
                    reihenfolge=antwort_position,
                )

        self.stdout.write(self.style.SUCCESS("Demo-Daten wurden erstellt."))
