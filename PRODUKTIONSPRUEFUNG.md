# Lokale Produktionspruefung

Stand: 2026-09-10. Ausschliesslich lokal getestet, kein Deployment.

## Payment

- `payment_aktiv` ist standardmaessig False, auch fuer bestehende Einstellungen nach Migration 0005.
- Migration lokal angewendet und Zustand False per Datenbankabfrage sowie im Browser bestaetigt.
- Aktivierung: Superadmin > Zahlungseinstellungen > Zahlungen aktivieren > Speichern.
- Superuser und Mitglieder der globalen Superadmin-Gruppe koennen den Schalter bedienen. Gewoehnliche Staff-/Org-Admin-Konten duerfen ihn nicht aendern.
- Neue Zahlungen sind auch direkt im Service gesperrt. Kostenlose Kurse, bestehende Einschreibungen, Rechnungen und die Abwicklung bereits eingegangener Ueberweisungen bleiben verfuegbar.
- Online-Anbieter bleiben in Produktion gesperrt, bis eine echte Integration existiert. Lokale Demo-Anbieter erfordern DEBUG und demo_autoconfirm. Manuelle Ueberweisung kann nach Aktivierung verwendet werden.
- CSRF-Schutz und Audit-Eintrag bei Schalterbedienung getestet.
- Sicherung vor Migration: `C:/Users/aborowczak/.codex/backups/DjangoProject/before-payment-switch-20260909-140751.sqlite3`, SQLite-Integritaetspruefung erfolgreich.

## Korrekturen

- Anonymer Checkout wird vor Zugriff auf Einschreibungen zum Login umgeleitet.
- Demo-Zahlungsbestaetigungen sind bei DEBUG=False ausgeschlossen.
- Demo-Datenkommando ist bei DEBUG=False gesperrt; es aktiviert Payment nicht automatisch.
- Demo-Zugangsdaten werden auf der Startseite bei DEBUG=False nicht mehr angezeigt. Bestehende Demo-Konten muessen vor dem Onlinebetrieb entfernt oder abgesichert werden.
- HSTS mit kurzer Anfangsdauer, nosniff und Referrer-Policy in Produktion gesetzt.
- Proxy-Vertrauen ist explizit opt-in und setzt einen kontrollierten Reverse Proxy voraus.
- SMTP-Konfiguration und Checks fuer unsichere Entwicklungswerte ergaenzt.
- Veraltete DEFAULT_FILE_STORAGE-Konfiguration durch STORAGES ersetzt.
- Widerspruechliche Django-Anforderungen auf die lokal getestete 5.2-Reihe vereinheitlicht (installiert: 5.2.15).

## Ergebnisse

- Gesamtlauf der bisherigen und neuen Payment-/Sicherheitstests: 53 Tests erfolgreich.
- Zusaetzlicher Lauf mit echten Produktionseinstellungen, temporaeren Schluesseln und isolierter Testdatenbank: 4 Tests erfolgreich. Geprueft: HTTPS-Weiterleitung, unbekannte Hosts, Header, sichere Cookies, echte CSRF-Pruefung, Superadmin-Schalter, oeffentliche Seiten, Dashboard und deaktivierter Checkout.
- `check`, `makemigrations --check --dry-run`, `collectstatic --dry-run` und `pip check`: erfolgreich.
- Headless Chrome: Startseite, Kurskatalog und Login jeweils HTTP 200, keine JavaScript-Ausnahmen. Superadmin-Login und Zahlungseinstellungen erfolgreich, Schalter ausgeschaltet.

Wiederholung lokal:

```powershell
.\.venv\Scripts\python.exe manage.py test --noinput
.\.venv\Scripts\python.exe deploy/test_production.py
```

Die vier Produktionstests werden im normalen Entwicklungslauf uebersprungen und durch den zweiten Befehl separat ausgefuehrt. Dieser nutzt keine produktiven Dienste und aendert die Projektdatenbank nicht.

Der lokale Deploy-Check meldet bewusst vier nicht unterdrueckte Warnungen: E-Mail wird im Speicher getestet, SQLite ersetzt den Zielserver, HSTS fuer alle Subdomains und HSTS-Preload sind noch nicht aktiviert. Diese HSTS-Optionen erst nach Festlegung und HTTPS-Pruefung aller betroffenen Domains entscheiden.

## Vor einem Onlinebetrieb noch erforderlich

- Ziel-Datenbank und echte HTTPS-/Reverse-Proxy-Konfiguration pruefen; Produktionsschluessel setzen und Demo-Konten absichern.
- SMTP-Zustellung testen. Der aktuelle Einladungserstellungs-View versendet noch keine Einladungsemail.
- Private Kursdateien absichern: Die Installationsskripte liefern `/media/` derzeit direkt aus. Dateiendungen und Groessenlimits ersetzen weder Zugriffskontrolle noch Malware-/Inhaltspruefung.
- Backup inklusive Medien und Encryption-Key auf dem Zielsystem wiederherstellen und pruefen. Die lokale Sicherung ersetzt diesen Wiederherstellungstest nicht.
- PDF-Rendering mit nativen Bibliotheken, S3, Installation unter Linux/IIS und Last-/Nebenlaeufigkeit auf dem Zielsystem pruefen. Insbesondere Rechnungsnummern sind noch nicht fuer hohe Parallelitaet abgesichert.
- Rechnungsanforderungen und verbleibende Rollen-/Mandantenzugriffe fachlich bzw. technisch pruefen.

Spaeterer strenger Zielserver-Check (benoetigt dort gesetzte Produktionsumgebung):

```powershell
python deploy/check_production.py
```

Er prueft Deploy-Warnungen, ausstehende Migrationen und statische Dateien ohne Migrationen anzuwenden. Grundlage: [Django Deployment Checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).

## Hinweis zum Gunicorn-Control-Socket

Serverlog vom 2026-09-10:

```text
Control server error: [Errno 1] Operation not permitted: '/var/www/clients/client2/web26/.gunicorn'
```

Gunicorn startet trotzdem und beantwortet Requests. Die Meldung entsteht, wenn Gunicorn keinen beschreibbaren Runtime-Pfad fuer den Control-Socket findet und deshalb auf `$HOME/.gunicorn/gunicorn.ctl` ausweicht. In der Linux-Installationsvorlage wird deshalb `XDG_RUNTIME_DIR=/run/aborolms` im systemd-Service gesetzt.

Bei der aktuellen ISPConfig-/Webkunden-Installation sollte die laufende Service-Datei entsprechend angepasst werden, zum Beispiel:

```ini
Environment=XDG_RUNTIME_DIR=/var/www/clients/client2/web26/tmp
```

Danach:

```bash
systemctl daemon-reload
systemctl restart <gunicorn-service-name>
journalctl -u <gunicorn-service-name> -n 50 --no-pager
```

Alternativ kann bei einer Gunicorn-Version mit Control-Socket-Unterstuetzung der Control-Socket explizit deaktiviert werden:

```bash
gunicorn --no-control-socket ...
```

Die `HEAD /`-Eintraege im Log sind weniger kritisch: `301` ist bei aktivem HTTPS-Redirect erwartbar. Die Meldung `WSGI app sent body bytes on a no-body response` bedeutet, dass ein HEAD-Request wie GET verarbeitet wurde und Gunicorn den Body korrekt verwirft.
