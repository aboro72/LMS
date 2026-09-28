import re
from html import escape, unescape

from django.utils.html import strip_tags
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


NAVY = colors.HexColor("#12315F")
ORANGE = colors.HexColor("#F28C28")
INK = colors.HexColor("#243449")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#DCE3EB")


class AnswerBox(Flowable):
    """Vector checkboxes stay crisp in print and need no special font glyphs."""

    def __init__(self, checked=False):
        super().__init__()
        self.checked = checked
        self.width = 12
        self.height = 12

    def draw(self):
        canvas = self.canv
        canvas.setStrokeColor(NAVY if self.checked else MUTED)
        canvas.setLineWidth(0.8)
        canvas.setFillColor(NAVY if self.checked else colors.white)
        canvas.roundRect(1, 1, 10, 10, 2, fill=1, stroke=1)
        if self.checked:
            canvas.setStrokeColor(colors.white)
            canvas.setLineWidth(1.3)
            path = canvas.beginPath()
            path.moveTo(3, 6)
            path.lineTo(5, 4)
            path.lineTo(9, 8)
            canvas.drawPath(path)


def _rich_text(html):
    """Keep paragraph boundaries and escape user content for ReportLab markup."""
    html = re.sub(r"<br\s*/?>|</(?:p|div|li|h[1-6])\s*>", "\n", html or "", flags=re.I)
    text = unescape(strip_tags(html))
    return "<br/>".join(escape(line.strip()) for line in text.splitlines() if line.strip())


def generiere_pruefungsbogen_pdf(pruefung, fragen, mit_loesungen=False):
    from io import BytesIO

    fragen = list(fragen)
    buffer = BytesIO()
    edition = "LÖSUNGSBOGEN" if mit_loesungen else "PRÜFUNGSBOGEN"
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2 * cm,
        title=f"{'Lösungsbogen' if mit_loesungen else 'Prüfungsbogen'} - {pruefung.titel}",
        author="ABoroLMS",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("ExamTitle", parent=styles["BodyText"], fontName="Helvetica-Bold", textColor=NAVY, fontSize=23, leading=28, spaceAfter=10)
    subtitle = ParagraphStyle("ExamSubtitle", parent=styles["BodyText"], textColor=MUTED, fontSize=10, leading=15, spaceAfter=14)
    question = ParagraphStyle("Question", parent=styles["BodyText"], fontName="Helvetica-Bold", textColor=INK, fontSize=11, leading=16, spaceBefore=7, spaceAfter=7)
    answer = ParagraphStyle("Answer", parent=styles["BodyText"], textColor=INK, fontSize=10, leading=14)
    correct = ParagraphStyle("Correct", parent=answer, fontName="Helvetica-Bold", textColor=NAVY)
    label = ParagraphStyle("Label", parent=answer, fontSize=8, leading=11, textColor=MUTED)
    points = ParagraphStyle("Points", parent=label, alignment=2, textColor=NAVY)
    note = ParagraphStyle("Note", parent=answer, fontSize=9.2, leading=13.5, backColor=colors.HexColor("#F1F5FA"), borderPadding=9, leftIndent=9, rightIndent=9, spaceBefore=12, spaceAfter=10)
    rubric = ParagraphStyle("Rubric", parent=note, backColor=colors.HexColor("#FFF5E8"))
    width = document.width

    def page_frame(canvas, doc):
        canvas.saveState()
        page_width, page_height = A4
        canvas.setFillColor(NAVY)
        canvas.rect(0, page_height - 7, page_width, 7, fill=1, stroke=0)
        canvas.setFillColor(ORANGE)
        canvas.rect(doc.leftMargin, page_height - 7, 40, 7, fill=1, stroke=0)
        canvas.setFillColor(NAVY)
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(doc.leftMargin, page_height - 39, "ABoroLMS")
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(page_width - doc.rightMargin, page_height - 37, edition)
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.6)
        canvas.line(doc.leftMargin, 43, page_width - doc.rightMargin, 43)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(doc.leftMargin, 29, "Prüferfassung · Vertraulich" if mit_loesungen else "Teilnehmerfassung · Zertifikatsprüfung")
        canvas.drawRightString(page_width - doc.rightMargin, 29, f"Seite {doc.page:02d}")
        canvas.restoreState()

    story = [Paragraph(escape(pruefung.titel), title)]
    story.append(Paragraph("Lösungen, fachliche Erläuterungen und Bewertungshinweise" if mit_loesungen else "Lesen Sie jede Aufgabe sorgfältig und tragen Sie Ihre Antworten ein.", subtitle))
    metrics = [("AUFGABEN", str(len(fragen))), ("GESAMTPUNKTE", str(sum(f.punkte for f in fragen))), ("BESTEHENSGRENZE", f"{pruefung.bestehensgrenze_prozent} %")]
    if pruefung.zeitlimit_minuten:
        metrics.append(("BEARBEITUNGSZEIT", f"{pruefung.zeitlimit_minuten} Min."))
    summary = Table([[Paragraph(f"{name}<br/><font size='14' color='#12315F'><b>{value}</b></font>", ParagraphStyle("Metric", parent=label, leading=20)) for name, value in metrics]], colWidths=[width / len(metrics)] * len(metrics))
    summary.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5FA")), ("BOX", (0, 0), (-1, -1), 0.5, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    story.extend([summary, Spacer(1, 20)])
    if not mit_loesungen:
        identity = Table([[Paragraph("<b>Name:</b> __________________________________", answer), Paragraph("<b>Datum:</b> __________________", answer)]], colWidths=[width * 0.63, width * 0.37])
        identity.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 15)]))
        story.append(identity)
    for nummer, frage in enumerate(fragen, start=1):
        block_start = len(story)
        heading = Table([[Paragraph(f"<b>AUFGABE {nummer:02d}</b>   /   {escape(frage.get_typ_display())}", label), Paragraph(f"<b>{frage.punkte} {'Punkt' if frage.punkte == 1 else 'Punkte'}</b>", points)]], colWidths=[width - 75, 75])
        heading.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.7, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        story.append(heading)
        text = _rich_text(frage.fragetext.html)
        story.append(Paragraph(text, question))
        if frage.typ in [frage.Typ.SINGLE_CHOICE, frage.Typ.MULTIPLE_CHOICE, frage.Typ.WAHR_FALSCH]:
            for antwort in frage.antworten.all():
                checked = mit_loesungen and antwort.ist_korrekt
                row = Table([[AnswerBox(checked), Paragraph(escape(unescape(antwort.antworttext)), correct if checked else answer)]], colWidths=[25, width - 25])
                row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5FA") if checked else colors.white)]))
                story.append(row)
        elif frage.typ == frage.Typ.ZUORDNUNG:
            for paar in frage.zuordnungen.all():
                right = escape(unescape(paar.rechtes_element)) if mit_loesungen else "................................................................"
                pair = Table([[Paragraph(escape(unescape(paar.linkes_element)), answer), Paragraph(right, correct if mit_loesungen else answer)]], colWidths=[width * 0.32, width * 0.68])
                pair.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
                story.append(pair)
        elif not mit_loesungen:
            writing = Table([[""] for _ in range(6)], colWidths=[width], rowHeights=22)
            writing.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE)]))
            story.append(writing)
        if mit_loesungen and (erklaerung := _rich_text(frage.erklaerung.html)):
            story.append(Paragraph("<b>Erklärung / Lösungshinweis:</b><br/>" + erklaerung, note))
        if mit_loesungen and frage.typ in [frage.Typ.FREITEXT, frage.Typ.SZENARIO] and frage.bewertungshinweis.html:
            schema = _rich_text(frage.bewertungshinweis.html)
            story.append(Paragraph(f"<b>Bewertungsschema (max. {frage.punkte} Punkte):</b><br/>{schema}", rubric))
        story.append(Spacer(1, 12))
        story[block_start:] = [KeepTogether(story[block_start:])]
    document.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    return buffer.getvalue()
