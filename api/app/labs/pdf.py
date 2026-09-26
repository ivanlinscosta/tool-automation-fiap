import contextlib
import io
from collections.abc import Iterator

import reportlab
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


PAGE_WIDTH, PAGE_HEIGHT = A4
DOCUMENT_TITLE = "Evidencia de Restore - Laudo Tecnico Ficticio"


@contextlib.contextmanager
def _invariant_output() -> Iterator[None]:
    previous = reportlab.rl_config.invariant
    reportlab.rl_config.invariant = 1
    try:
        yield
    finally:
        reportlab.rl_config.invariant = previous


def _render_screenshot_png(width: int = 560, height: int = 260) -> ImageReader:
    image = Image.new("RGB", (width, height), color=(248, 249, 251))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, width - 1, height - 1], outline=(90, 98, 112), width=2)
    draw.rectangle([2, 2, width - 3, 26], fill=(64, 72, 88))
    for offset, shade in enumerate(((214, 90, 90), (226, 178, 82), (118, 186, 122))):
        draw.ellipse([14 + offset * 20, 9, 24 + offset * 20, 19], fill=shade)
    draw.text((90, 10), "Restore Manager - sessao ficticia", fill=(236, 238, 242))
    draw.line([12, 40, width - 12, 40], fill=(200, 205, 214))
    draw.text((16, 52), "IC: IC-000000", fill=(38, 44, 56))
    draw.text((16, 74), "Ticket: CHG-000000", fill=(38, 44, 56))
    draw.text((16, 96), "Resultado: CONFORME", fill=(24, 118, 66))
    draw.rectangle([16, 122, width - 16, height - 16], outline=(160, 168, 180))
    for row in range(6):
        y = 136 + row * 18
        draw.line([26, y, width - 26 - (row % 3) * 40, y], fill=(176, 184, 196))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return ImageReader(buffer)


def build_evidence_pdf(
    *,
    evidence_id: str,
    ic: str,
    ticket_mudanca: str,
    data_hora_teste: str,
    resultado: str,
    has_prints: bool,
    divergent_fields: list[str],
    missing_fields: list[str],
) -> bytes:
    buffer = io.BytesIO()
    with _invariant_output():
        document = canvas.Canvas(buffer, pagesize=A4)
        document.setTitle(DOCUMENT_TITLE)
        document.setAuthor("Quantum Commerce Workflow Labs")

        document.setFont("Helvetica-Bold", 16)
        document.drawString(48, PAGE_HEIGHT - 56, DOCUMENT_TITLE)
        document.setFont("Helvetica", 9)
        document.drawString(48, PAGE_HEIGHT - 72, "Documento ficticio gerado para a disciplina Tools, Automations and Workflows - FIAP")
        document.setLineWidth(1)
        document.line(48, PAGE_HEIGHT - 82, PAGE_WIDTH - 48, PAGE_HEIGHT - 82)

        document.setFont("Helvetica-Bold", 12)
        document.drawString(48, PAGE_HEIGHT - 108, "Identificacao da evidencia")
        document.setFont("Helvetica", 11)
        fields = [
            ("Evidence ID", evidence_id),
            ("IC", ic),
            ("Ticket / Mudanca", ticket_mudanca),
            ("Data / Hora do Teste", data_hora_teste),
            ("Resultado", resultado),
        ]
        y = PAGE_HEIGHT - 130
        for label, value in fields:
            document.setFont("Helvetica-Bold", 10)
            document.drawString(60, y, f"{label}:")
            document.setFont("Helvetica", 10)
            if value:
                document.drawString(190, y, str(value))
            else:
                document.setFillGray(0.45)
                document.drawString(190, y, "(campo ausente no documento)")
                document.setFillGray(0)
            y -= 18

        if divergent_fields:
            document.setFont("Helvetica-Bold", 11)
            document.drawString(48, y - 8, "Divergencias anotadas pelo laboratorio")
            document.setFont("Helvetica", 9)
            y -= 26
            for field in divergent_fields:
                document.drawString(60, y, f"- {field}")
                y -= 14

        if has_prints:
            document.setFont("Helvetica-Bold", 11)
            document.drawString(48, y - 10, "Print do restore (simulado)")
            image = _render_screenshot_png()
            document.drawImage(image, 48, max(96, y - 10 - 260), width=560, height=260, mask="auto")
        else:
            document.setFont("Helvetica-Bold", 11)
            document.drawString(48, y - 10, "Print do restore (simulado)")
            document.setFont("Helvetica-Oblique", 10)
            document.drawString(48, y - 30, "Nenhum print anexado a esta evidencia.")

        document.setFont("Helvetica", 8)
        document.drawString(48, 42, "Fiction lab document - not a real production record.")
        document.showPage()
        document.save()
    return buffer.getvalue()
