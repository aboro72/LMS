import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tmp/pdf-tools"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django
django.setup()

from pypdf import PdfReader
import pypdfium2 as pdfium
from PIL import Image, ImageOps, ImageDraw
from apps.exams.models import Pruefung
from apps.exams.pdf import generiere_pruefungsbogen_pdf

exam = Pruefung.objects.get(
    titel="ABoroLMS Grundlagen Zertifikatspruefung",
    organisation__slug="demo-organisation",
)
questions = list(exam.fragenkatalog.fragen.prefetch_related("antworten", "zuordnungen"))
assert len(questions) == 13
assert all(q.erklaerung.html for q in questions)
out = ROOT / "tmp/pdfs"
previews = []
for solutions, name in ((True, "loesungsbogen"), (False, "teilnehmerbogen")):
    path = out / f"{name}.pdf"
    path.write_bytes(generiere_pruefungsbogen_pdf(exam, questions, mit_loesungen=solutions))
    reader = PdfReader(path)
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert text.count("Erklärung / Lösungshinweis:") == (13 if solutions else 0)
    assert ("Maximal 3 Punkte" in text) == solutions
    document = pdfium.PdfDocument(path)
    for i, page in enumerate(document):
        picture = page.render(scale=1.3).to_pil().convert("RGB")
        picture.save(out / f"{name}-{i + 1}.png")
        preview = ImageOps.expand(picture, border=(8, 28, 8, 8), fill="lightgray")
        ImageDraw.Draw(preview).text((10, 8), f"{name} Seite {i + 1}", fill="black")
        previews.append(preview)
    print(f"{name}: {len(reader.pages)} Seiten, Textpruefung erfolgreich")
width = max(p.width for p in previews)
height = max(p.height for p in previews)
sheet = Image.new("RGB", (width * 3, height * ((len(previews) + 2) // 3)), "gray")
for i, preview in enumerate(previews):
    sheet.paste(preview, ((i % 3) * width, (i // 3) * height))
sheet.save(out / "overview.png")
