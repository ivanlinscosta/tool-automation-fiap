import io
import re
import zipfile
from datetime import datetime
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font


FIXED_DOCUMENT_DATETIME = datetime(2026, 1, 1, 0, 0, 0)
FIXED_ZIP_DATE_TIME = (2026, 1, 1, 0, 0, 0)
FIXED_ISO_DATETIME = b"2026-01-01T00:00:00Z"
MODIFIED_PATTERN = re.compile(rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)")
DOCUMENT_AUTHOR = "Quantum Commerce Workflow Labs"


def _normalize_xlsx(payload: bytes) -> bytes:
    source = io.BytesIO(payload)
    target = io.BytesIO()
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            entry = zipfile.ZipInfo(info.filename, FIXED_ZIP_DATE_TIME)
            entry.compress_type = info.compress_type
            entry.external_attr = info.external_attr
            data = src.read(info.filename)
            if info.filename == "docProps/core.xml":
                data = MODIFIED_PATTERN.sub(
                    lambda match: match.group(1) + FIXED_ISO_DATETIME + match.group(2),
                    data,
                )
            dst.writestr(entry, data)
    return target.getvalue()


def build_xlsx(
    sheet_name: str,
    headers: list[str],
    rows: list[list[Any]],
    *,
    column_widths: dict[int, int] | None = None,
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name[:31]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append(row)
    for index, width in (column_widths or {}).items():
        letter = sheet.cell(row=1, column=index).column_letter
        sheet.column_dimensions[letter].width = width
    workbook.properties.created = FIXED_DOCUMENT_DATETIME
    workbook.properties.modified = FIXED_DOCUMENT_DATETIME
    workbook.properties.creator = DOCUMENT_AUTHOR
    workbook.properties.lastModifiedBy = DOCUMENT_AUTHOR
    buffer = io.BytesIO()
    workbook.save(buffer)
    return _normalize_xlsx(buffer.getvalue())
