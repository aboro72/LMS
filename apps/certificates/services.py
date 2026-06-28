import base64
import io

import qrcode
from django.template.loader import render_to_string


def stelle_zertifikat_aus(pruefungsversuch):
    from .models import Zertifikat

    if not pruefungsversuch.bestanden:
        return None
    zert, _ = Zertifikat.objects.get_or_create(
        nutzer=pruefungsversuch.nutzer,
        pruefungsversuch=pruefungsversuch,
    )
    return zert


def _generiere_qr_code_b64(url):
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _lade_design(organisation):
    from .models import ZertifikatDesign

    if organisation is None:
        from types import SimpleNamespace
        return SimpleNamespace(
            primary_color="#12315f",
            secondary_color="#f28c28",
            org_display_name="",
            footer_text="",
            signature_line="",
            logo=None,
        )
    design, _ = ZertifikatDesign.objects.get_or_create(organisation=organisation)
    return design


def _logo_b64(design):
    if not design.logo:
        return None
    try:
        with open(design.logo.path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        ext = design.logo.name.rsplit(".", 1)[-1].lower()
        mime = "image/png" if ext == "png" else "image/jpeg"
        return f"data:{mime};base64,{data}"
    except (FileNotFoundError, AttributeError, ValueError):
        return None


def generiere_zertifikat_pdf(zertifikat, base_url):
    # Lazy import: WeasyPrint benötigt GTK-Systemlibaries (Windows: GTK-Runtime installieren)
    try:
        from weasyprint import HTML
    except OSError as exc:
        raise RuntimeError(
            "WeasyPrint konnte GTK-Bibliotheken nicht laden. "
            "Bitte installiere die GTK3-Runtime fuer Windows: "
            "https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows"
        ) from exc

    org = zertifikat.get_organisation()
    design = _lade_design(org)
    verify_url = f"{base_url.rstrip('/')}/zertifikate/verify/{zertifikat.code}/"
    qr_b64 = _generiere_qr_code_b64(verify_url)
    org_name = design.org_display_name or (org.name if org else "ABoroLMS")
    html_string = render_to_string(
        "certificates/pdf.html",
        {
            "zertifikat": zertifikat,
            "verify_url": verify_url,
            "qr_b64": qr_b64,
            "primary_color": design.primary_color,
            "secondary_color": design.secondary_color,
            "org_name": org_name,
            "footer_text": design.footer_text,
            "signature_line": design.signature_line,
            "logo_b64": _logo_b64(design),
        },
    )
    return HTML(string=html_string).write_pdf()
