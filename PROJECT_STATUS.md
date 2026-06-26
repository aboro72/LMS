# ABoroLMS Projektstatus

## Erledigt

- Produktannahme aktualisiert: ABoroLMS wird als Selfhosting-Produkt geplant, nicht als reines SaaS-Angebot.
- Branding aktualisiert: ABoroSoft wird vorerst ohne GmbH-Bezeichnung gefuehrt.
- Spaeterer Installationsumfang vorgemerkt: GitHub-basierte Installationsskripte fuer Linux mit Apache2 oder Nginx sowie alternativ Windows mit IIS.
- Projektstruktur fuer Phase 1 begonnen: `config`, `apps`, `templates`, `static`, `requirements`, `media`.
- Bestehendes Startprojekt `djangoproject` wurde durch `config` als Django-Projektmodul ersetzt.
- `manage.py` zeigt auf `config.settings.development`.
- Custom User, Rollen, UserProfile, Organisation und Einladung sind modelliert.
- Admin, Auth-Routing, Registrierung, Dashboard, Base-Templates und ABoroLMS-CSS sind angelegt.
- Initial-Migrations fuer `accounts` und `organisations` sind vorhanden.
- Entwicklungsabhaengigkeiten wurden in `.venv` installiert.
- `python manage.py check`, `makemigrations --check --dry-run` und `migrate` wurden erfolgreich ausgefuehrt.
- Phase 2 umgesetzt: `courses`-App mit Kurs, Abschnitt, Lektion, Einschreibung und Lektionsfortschritt.
- Kurs-Katalog, Kurs-Detailseite, Einschreibung, Lerninterface und Trainer-Kursverwaltung sind angelegt.
- Demo-Daten enthalten jetzt eine Demo-Organisation, Rollen-Nutzer und einen veroeffentlichten Beispielkurs.
- Demo-Daten enthalten einen Benutzer je Rolle; die Zugangsdaten werden auf der Startseite angezeigt.
- Phase 2 wurde validiert: `check`, Migration, Demo-Command und Smoke-Tests fuer Katalog, Detail, Lernen und Trainerseiten.
- Demo-Kurs `ABoroLMS Grundlagen` ist mit der Zertifikatspruefung `ABoroLMS Grundlagen Zertifikatspruefung` verbunden.
- Demo-Kurs `ABoroLMS Grundlagen` enthaelt 4 Abschnitte und 8 vorbereitende Lerneinheiten passend zur Zertifikatspruefung.
- Kurslektionen unterstuetzen Video-Uploads fuer Selfhosting: Trainer koennen MP4/WebM/MOV/M4V hochladen oder eine Video-URL hinterlegen.
- Lerninterface spielt hochgeladene Videos ueber HTML5-Video ab und zeigt bei fehlender Videodatei einen Platzhalter.
- Lektionen unterstuetzen mehrere Begleitmaterialien sowie optionale Multiple-Choice-Uebungsfragen zur Lernfortschrittspruefung.
- Demo-Kurs enthaelt jetzt 8 Uebungsfragen, 24 Uebungsantworten und 2 Begleitmaterialien.
- Bezahlte Kurse werden ueber eine Payment-App abgebildet: Stripe, Google Pay, PayPal und Ueberweisung sind als Zahlungsarten vorhanden.
- Zahlungsanbieter und optionale API-Keys koennen in den Django-Admin-Zahlungseinstellungen aktiviert und gepflegt werden.
- Nach bestaetigter Zahlung wird die Einschreibung bezahlt markiert und der Kurs dauerhaft freigeschaltet.
- Zahlungen laufen zentral ein; pro Zahlung werden 15% Plattformgebuehr und 85% Trainer-Anteil fest gespeichert.
- Superadmin-Auszahlungsuebersicht zeigt offene Trainer-Summen und erlaubt manuelle Bestaetigung von Ueberweisungen sowie Auszahlungstracking.
- Demo-Kurs `ABoroLMS Grundlagen` kostet 49 EUR; Demo-Zahlungen zeigen 7,35 EUR Plattformgebuehr und 41,65 EUR Trainer-Anteil.
- Demo-Pruefung enthaelt 8 Fragen und 30 Antworten mit plausiblen falschen Antworten und passenden richtigen Antworten.
- Pruefungsdetail, Pruefungsstart, Durchfuehrungsseite und Ergebnisansicht sind fuer den Demo-Fluss angelegt.
- RollenMixin leitet anonyme Nutzer jetzt korrekt zum Login weiter, statt auf `AnonymousUser.profile` zuzugreifen.

## Aktuell in Arbeit

- Phase 2 ist abgeschlossen.

## Noch offen

- Installationsskripte fuer Selfhosting: Linux Apache2, Linux Nginx, optional Windows IIS.
- Phase 3: Pruefungssystem weiter ausbauen, insbesondere Trainer-Templates, CSV-Import-UI, Examiner-Queue und Tests.
- Phase 4: Zertifizierung.
- Phase 5: SaaS-Features.
