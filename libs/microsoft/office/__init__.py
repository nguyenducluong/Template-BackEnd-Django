"""libs.microsoft.office — đọc file văn phòng Microsoft Office.

Mối loại đọc, đều có 2 backend:
    1. Thư viện Python (mac định) — chạy được headless / Linux / Docker.
    2. COM (fallback) — chỉ khi thư viện lỗi, cần Windows + cái MS Office.

    from libs.microsoft.office import read_excel, read_word, read_powerpoint, read_pdf
"""

from libs.microsoft.office.errors import (
    ExcelBackendUnavailable,
    ExcelError,
    ExcelFileNotFound,
    ExcelSheetNotFound,
    PdfBackendUnavailable,
    PdfFileNotFound,
    PowerPointBackendUnavailable,
    PowerPointFileNotFound,
    WordBackendUnavailable,
    WordFileNotFound,
)
from libs.microsoft.office.reader import read_excel
from libs.microsoft.office.pdf import read_pdf
from libs.microsoft.office.powerpoint import read_powerpoint
from libs.microsoft.office.word import read_word

__all__ = [
    # doc file
    "read_excel",
    "read_word",
    "read_powerpoint",
    "read_pdf",
    # exception (Excel + Word + PowerPoint + PDF)
    "ExcelError",
    "ExcelFileNotFound",
    "ExcelSheetNotFound",
    "ExcelBackendUnavailable",
    "WordFileNotFound",
    "WordBackendUnavailable",
    "PowerPointFileNotFound",
    "PowerPointBackendUnavailable",
    "PdfFileNotFound",
    "PdfBackendUnavailable",
]
