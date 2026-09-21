"""Local production-settings smoke test with ephemeral secrets and test database.

No production service is contacted; the project database is never used.
"""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

from cryptography.fernet import Fernet


def main():
    root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix="aborolms-production-test-") as directory:
        env = os.environ.copy()
        env.update(
            DJANGO_SETTINGS_MODULE="config.settings.production",
            DB_ENGINE="postgresql",
            DATABASE_URL="sqlite:///" + (Path(directory) / "test.sqlite3").as_posix(),
            SECRET_KEY=secrets.token_urlsafe(64),
            FIELD_ENCRYPTION_KEY=Fernet.generate_key().decode(),
            ALLOWED_HOSTS="testserver,localhost,127.0.0.1",
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            EMAIL_USE_TLS="True",
            EMAIL_USE_SSL="False",
            AWS_STORAGE_BUCKET_NAME="",
            SECURE_SSL_REDIRECT="True",
            SECURE_HSTS_SECONDS="3600",
            SECURE_HSTS_INCLUDE_SUBDOMAINS="False",
            SECURE_HSTS_PRELOAD="False",
            TRUST_PROXY_SSL_HEADER="False",
        )
        commands = (
            ["check", "--deploy"],
            ["test", "apps.security.test_production_smoke", "--noinput"],
            ["collectstatic", "--dry-run", "--noinput", "--verbosity", "0"],
        )
        for command in commands:
            print("Lokaler Produktionstest: " + " ".join(command), flush=True)
            result = subprocess.run([sys.executable, str(root / "manage.py"), *command], cwd=root, env=env)
            if result.returncode:
                return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
