import dj_database_url

from .base import *  # noqa: F403

DEBUG = False

# --------------------------------------------------------------------------- #
# Datenbankmotor
# DB_ENGINE: postgresql | mysql | mssql | mongodb
# --------------------------------------------------------------------------- #
DB_ENGINE = config("DB_ENGINE", default="postgresql")  # noqa: F405

if DB_ENGINE == "mssql":
    DATABASES = {
        "default": {
            "ENGINE": "mssql",
            "NAME": config("DB_NAME"),  # noqa: F405
            "USER": config("DB_USER"),  # noqa: F405
            "PASSWORD": config("DB_PASSWORD"),  # noqa: F405
            "HOST": config("DB_HOST", default="localhost"),  # noqa: F405
            "PORT": config("DB_PORT", default="1433"),  # noqa: F405
            "OPTIONS": {
                "driver": "ODBC Driver 17 for SQL Server",
                "unicode_results": True,
            },
        }
    }
elif DB_ENGINE == "mongodb":
    DATABASES = {
        "default": {
            "ENGINE": "django_mongodb_backend",
            "NAME": config("DB_NAME"),  # noqa: F405
            "HOST": config("DB_HOST", default="localhost"),  # noqa: F405
            "PORT": config("DB_PORT", default=27017, cast=int),  # noqa: F405
            "USER": config("DB_USER", default=""),  # noqa: F405
            "PASSWORD": config("DB_PASSWORD", default=""),  # noqa: F405
        }
    }
elif DB_ENGINE == "mysql":
    # PyMySQL als reines Python-Fallback, falls mysqlclient nicht kompiliert
    try:
        import MySQLdb  # noqa: F401 – mysqlclient vorhanden
    except ImportError:
        import pymysql
        pymysql.install_as_MySQLdb()
    DATABASES = {
        "default": dj_database_url.config(
            default=config("DATABASE_URL"),  # noqa: F405
            conn_max_age=600,
        )
    }
else:
    # postgresql (Standard)
    DATABASES = {
        "default": dj_database_url.config(
            default=config("DATABASE_URL"),  # noqa: F405
            conn_max_age=600,
        )
    }

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)  # noqa: F405

if config("AWS_STORAGE_BUCKET_NAME", default=""):  # noqa: F405
    INSTALLED_APPS += ["storages"]  # noqa: F405
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="")  # noqa: F405
    AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="")  # noqa: F405
    AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME")  # noqa: F405
