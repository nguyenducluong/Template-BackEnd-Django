"""Doc file PDF theo path - 2 backend: pypdf va COM (Word that).

BACKEND
-------
1. pypdf (mac dinh) - thuan Python, chay duoc headless / Linux / Docker.
2. win32com (fallback) - chi khi pypdf doc loi (VD PDF bao ve, PDF scan) VA may
   dang cai MS Office. Can ``pywin32``.

VSAI COM DUNG GI?
----------------
PDF khong phai dinh dang cua Office nen khong co "PDF.Application". Backend COM
dung **Word** de mo PDF: Word 2013+ tu chuyen PDF sang layout van ban, giu duoc
text. Do do ket qua fallback co them nhieu dong thuong va bo cuc - **pypdf la
mac dinh** va la lua chon dung khi can text chinh xac.

PDF co xac thuc / bao ve (encrypted): ``extract_text`` tra chuoi rong. Truong hop
nay can mat khoa truoc - xem ``decrypt(password)`` hoac doc bang ngoai.

Ket qua: ``{"pages": [{"index": 1, "text": str}], "text": str, "encrypted": bool}``.
"""

import logging

from libs.microsoft.office._common import has_com, require_file, run_com
from libs.microsoft.office.errors import PdfBackendUnavailable, PdfFileNotFound

logger = logging.getLogger("apps")


# --- backend 1: pypdf (mac dinh) ---


def _read_pdf_python(file_path, password=None):
    """Doc PDF bang pypdf -> dict {pages, text, encrypted}."""
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    encrypted = bool(reader.is_encrypted)
    # File bao ve: can mat khoa truoc khi extract_text duoc
    if encrypted and password is not None:
        try:
            reader.decrypt(password)
            encrypted = bool(reader.is_encrypted)
        except Exception:  # pragma: no cover - sai mat khau
            pass

    pages = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception:  # pragma: no cover - trang hong
            text = ""
        pages.append({"index": index, "text": text})

    return {"pages": pages, "text": "\n".join(p["text"] for p in pages), "encrypted": encrypted}


# --- backend 2: win32com (fallback, dung Word de mo PDF) ---


def _read_pdf_com(file_path, password=None):
    """Doc PDF bang COM (Word tu convert PDF sang van ban) -> dict."""

    def work(app):
        app.Visible = False
        # Word 2013+ tu nhan dien PDF. ConfirmConversions=False de khong hoi nguoi dung.
        document = app.Documents.Open(
            file_path,
            ReadOnly=True,
            ConfirmConversions=False,
            AddToRecentFiles=False,
        )
        try:
            text = str(document.Content.Text or "").strip()
            return {"pages": [{"index": 1, "text": text}], "text": text, "encrypted": False}
        finally:
            document.Close(False)

    return run_com("Word.Application", work)


# --- API cong khai ---


def read_pdf(file_path, password=None, with_com_fallback=True):
    """Doc file PDF va tra ve du lieu JSON-serializable.

    Args:
        file_path (str): duong dan file .pdf.
        password (str|None): mat khau cho PDF bao ve (truoc khi truy xuat text).
        with_com_fallback (bool): ``True`` -> pypdf loi thi thu COM (Word).
            ``False`` -> chi dung pypdf (nhanh hon, khong can MS Office).

    Returns:
        dict: ``{"pages": [{"index": 1, "text": str}, ...], "text": str, "encrypted": bool}``

    Raises:
        PdfFileNotFound: file khong ton tai.
        PdfBackendUnavailable: khong backend nao doc duoc.

    Vi du:
        >>> doc = read_pdf("D:/data/hop-dong.pdf")
        >>> doc["pages"][0]["text"]
    """
    require_file(file_path, PdfFileNotFound)

    try:
        return _read_pdf_python(file_path, password)
    except Exception as python_error:
        logger.warning("pypdf failed to read %s (%s)", file_path, python_error)
        if not with_com_fallback:
            raise PdfBackendUnavailable(
                "Cannot read PDF: {} (pypdf failed: {}; COM fallback disabled)".format(file_path, python_error)
            ) from python_error
        if not has_com():
            raise PdfBackendUnavailable(
                "Cannot read PDF: {} (pypdf failed: {}; pywin32 not available "
                "so COM fallback is skipped)".format(file_path, python_error)
            ) from python_error
        try:
            return _read_pdf_com(file_path, password)
        except PdfFileNotFound:
            raise
        except Exception as com_error:
            raise PdfBackendUnavailable(
                "Cannot read PDF: {} (pypdf: {}; COM: {})".format(file_path, python_error, com_error)
            ) from com_error