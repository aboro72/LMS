from django.conf import settings
from django.core.checks import Error, Warning, register

from .crypto import get_field_fernet


@register()
def field_encryption_key_check(app_configs, **kwargs):
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "")
    if not key:
        if getattr(settings, "DEBUG", False):
            return [Warning(
                "FIELD_ENCRYPTION_KEY ist nicht gesetzt. Verschluesselte Felder koennen nicht produktiv genutzt werden.",
                id="aborolms.W001",
            )]
        return [Error(
            "FIELD_ENCRYPTION_KEY muss in Produktion gesetzt sein.",
            id="aborolms.E001",
        )]
    try:
        get_field_fernet()
    except Exception as exc:
        return [Error(str(exc), id="aborolms.E002")]
    return []