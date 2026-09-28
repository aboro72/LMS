# ABoroLMS Installation und ISPConfig3/Nginx

## Ziel

ABoroLMS kann direkt über eine IP-Adresse, über einen einzelnen Hostnamen oder hinter einem Reverse Proxy wie ISPConfig3/Nginx betrieben werden.

Die Mandantenzuordnung funktioniert über:

- eine registrierte Mandantendomäne, z. B. `kunde-a.example.de`, oder
- den bestehenden Pfadzugriff, z. B. `http://203.0.113.10/kunde-a/`.

Ein Hostname wird niemals allein aufgrund eines beliebigen `Host`-Headers einem Mandanten zugeordnet. Er muss als aktive Mandantendomäne registriert sein.

## 1. Installation auf Debian/Ubuntu

Als Root ausführen:

```bash
sudo bash deploy/install-linux.sh \
  --repo https://github.com/ORGANISATION/LMS.git \
  --domain lms.example.de \
  --db postgresql
```

Das Skript installiert Python, PostgreSQL, Nginx, Gunicorn und die Python-Abhängigkeiten, richtet Migrationen und einen systemd-Dienst ein und erzeugt einen einmaligen Installations-Token.

Danach die ausgegebene URL öffnen:

```text
https://lms.example.de/install/?token=...
```

Der Web-Assistent legt die erste Organisation, die erste Domain/IP, den Superuser und das Org-Admin-Profil an. Nach erfolgreichem Abschluss ist der Installer gesperrt. Der Token darf nicht weitergegeben oder in Tickets/Logs veröffentlicht werden.

Der Web-Assistent installiert bewusst keine Betriebssystempakete und arbeitet nicht mit Root-Rechten. Diese Aufgabe bleibt dem Bootstrap-Skript vorbehalten.

## 2. Direkter Betrieb über eine IP-Adresse

Für einen direkten Testzugriff reicht:

```text
http://203.0.113.10/
```

Für mehrere Mandanten wird der Pfad verwendet:

```text
http://203.0.113.10/kunde-a/
http://203.0.113.10/kunde-b/
```

Der Wert `203.0.113.10` muss in `ALLOWED_HOSTS` stehen. Für produktiven Betrieb sollte HTTPS vor der IP oder ein DNS-Name verwendet werden.

## 3. ISPConfig3 und Nginx als Reverse Proxy

1. In ISPConfig eine Website für den öffentlichen Hostnamen anlegen.
2. SSL/Let's Encrypt dort aktivieren.
3. Den Inhalt aus [`deploy/ispconfig-nginx.conf.example`](deploy/ispconfig-nginx.conf.example) als Custom-Nginx-Konfiguration verwenden.
4. Den Socket-Pfad an die Installation anpassen, falls `APP_DIR` nicht `/opt/aborolms` ist.
5. In der ABoroLMS-`.env` setzen:

```dotenv
ALLOWED_HOSTS=lms.example.de,kunde-a.example.de,127.0.0.1
USE_X_FORWARDED_HOST=True
TRUST_PROXY_SSL_HEADER=True
CSRF_TRUSTED_ORIGINS=https://lms.example.de,https://kunde-a.example.de
SECURE_SSL_REDIRECT=True
```

Der Proxy muss mindestens diese Header setzen und darf sie nicht vom Client ungeprüft übernehmen:

```nginx
proxy_set_header Host $host;
proxy_set_header X-Forwarded-Host $host;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Real-IP $remote_addr;
```

Danach:

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl restart aborolms
```

## 4. Mandantendomänen registrieren

Nach der Installation können Domains im Django-Admin unter einer Organisation als „Mandantendomänen“ hinterlegt werden. Für jede Domain gilt:

- vollständiger Hostname ohne `http://` und ohne Pfad,
- kleingeschrieben,
- genau eine Organisation,
- nur aktive Einträge werden ausgewertet.

Beispiele:

```text
kunde-a.example.de
training.kunde-a.de
```

Die Domain muss zusätzlich im DNS auf den ISPConfig-/Nginx-Server zeigen und dort als Website/ServerAlias hinterlegt sein.

## 5. Sicherheit

- `ALLOWED_HOSTS` niemals auf `*` setzen.
- `USE_X_FORWARDED_HOST` nur aktivieren, wenn ausschließlich ein vertrauenswürdiger Proxy vor Django steht.
- `SECURE_PROXY_SSL_HEADER` nicht aktivieren, wenn Django direkt aus dem Internet erreichbar ist und Clients den Forwarded-Header selbst setzen können.
- Den Installations-Token nach Abschluss aus der `.env` entfernen und den Dienst neu starten.
- `/media/` sollte bei vertraulichen Prüfungsdateien nicht öffentlich ausgeliefert werden; dafür ist eine geschützte Download-View mit Berechtigungsprüfung erforderlich.
- Backups von `.env`, Datenbank und `media/` erstellen.

## 6. Betrieb prüfen

```bash
sudo systemctl status aborolms
sudo journalctl -u aborolms -n 100 --no-pager
sudo nginx -t
```

Django-Prüfung:

```bash
cd /opt/aborolms
sudo -u aborolms .venv/bin/python manage.py check --deploy --settings=config.settings.production
```

## 7. Aktualisierung

```bash
cd /opt/aborolms
sudo -u aborolms git pull --ff-only
sudo -u aborolms .venv/bin/pip install -r requirements/production.txt
sudo -u aborolms .venv/bin/python manage.py migrate --noinput --settings=config.settings.production
sudo -u aborolms .venv/bin/python manage.py collectstatic --noinput --settings=config.settings.production
sudo systemctl restart aborolms
```
