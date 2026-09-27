"""Lỗi của libs.microsoft.office (Excel).

Thay cho kiểu ``print(json) + sys.exit`` của script CLI gốc: thư viện nên NÉM
exception để view/service bắt được, còn CLI chỉ là lớp bọc mỏng phía ngoài.
"""


class ExcelError(Exception):
    """Lỗi chung của mọi thao tác đọc Excel."""


class ExcelFileNotFound(ExcelError):
    """Không tìm thấy file Excel tại path đưa vào."""


class ExcelSheetNotFound(ExcelError):
    """File tồn tại nhưng không có sheet được chỉ định."""


class ExcelBackendUnavailable(ExcelError):
    """Không backend nào đọc được file (openpyxl hỏng VÀ không có COM để fallback)."""

# ---- Word (.docx) ----


class WordFileNotFound(ExcelFileNotFound):
    """Khong tim thay file Word."""


class WordBackendUnavailable(ExcelBackendUnavailable):
    """Khong backend nao doc duoc file Word."""


# ---- PowerPoint (.pptx) ----


class PowerPointFileNotFound(ExcelFileNotFound):
    """Khong tim thay file PowerPoint."""


class PowerPointBackendUnavailable(ExcelBackendUnavailable):
    """Khong backend nao doc duoc file PowerPoint."""


# ---- PDF ----


class PdfFileNotFound(ExcelFileNotFound):
    """Khong tim thay file PDF."""


class PdfBackendUnavailable(ExcelBackendUnavailable):
    """Khong backend nao doc duoc file PDF."""
