"""Doc file Word (.docx) theo path - 2 backend: python-docx va COM (Word that).

BACKEND
-------
1. python-docx (mac dinh) - thuan Python, chay duoc headless / Linux / Docker.
2. win32com (fallback) - chi khi python-docx doc loi (VD .doc cu, file mac dinh
   khac) VA may dang cai MS Word. Can ``pywin32``.

Ket qua gom 3 phan: ``paragraphs`` (doan van ban), ``tables`` (bang), ``text``
(toan bo chuoi de tien xu ly).

DOCX CO MERGE / BANG CHONG NHAU: python-docx de nhin text da gop san (giong
COM) nen khong can logic lap merge nhu Excel.
"""

import logging

from libs.microsoft.office._common import has_com, require_file, run_com, to_text
from libs.microsoft.office.errors import WordBackendUnavailable, WordFileNotFound

logger = logging.getLogger("apps")


# --- backend 1: python-docx (mac dinh) ---


def _read_docx_python(file_path, with_tables=True):
    """Doc .docx bang python-docx -> dict {paragraphs, tables, text}."""
    from docx import Document

    document = Document(file_path)
    paragraphs = [to_text(p.text) for p in document.paragraphs]

    tables = []
    if with_tables:
        for table in document.tables:
            for row in table.rows:
                tables.append([to_text(cell.text) for cell in row.cells])

    return {"paragraphs": paragraphs, "tables": tables, "text": "\n".join(paragraphs)}


# --- backend 2: win32com (fallback) ---


def _read_docx_com(file_path, with_tables=True):
    """Doc .docx bang COM (Word that) -> dict {paragraphs, tables, text}."""

    def work(app):
        app.Visible = False
        document = app.Documents.Open(file_path, ReadOnly=True)
        try:
            text = to_text(document.Content.Text)
            paragraphs = [to_text(p.Range.Text) for p in document.Paragraphs]
            tables = []
            if with_tables:
                for table in document.Tables:
                    for row in table.Rows:
                        tables.append([to_text(cell.Range.Text) for cell in row.Cells])
            return {"paragraphs": paragraphs, "tables": tables, "text": text}
        finally:
            document.Close(False)

    return run_com("Word.Application", work)


# --- API cong khai ---


def read_word(file_path, with_tables=True):
    """Doc file Word va tra ve du lieu JSON-serializable.

    Args:
        file_path (str): duong dan file .docx (hoac .doc neu co MS Word).
        with_tables (bool): ``True`` -> trich xuat ca bang trong tai lieu.

    Returns:
        dict: ``{"paragraphs": [...], "tables": [[cell, ...], ...], "text": str}``

    Raises:
        WordFileNotFound: file khong ton tai.
        WordBackendUnavailable: khong backend nao doc duoc.

    Vi du:
        >>> doc = read_word("D:/data/hop-dong.docx")
        >>> doc["text"]
    """
    require_file(file_path, WordFileNotFound)

    try:
        return _read_docx_python(file_path, with_tables)
    except Exception as python_error:
        logger.warning(
            "python-docx failed to read %s (%s) - trying COM fallback",
            file_path,
            python_error,
        )
        if not has_com():
            raise WordBackendUnavailable(
                "Cannot read Word file: {} (python-docx failed: {}; "
                "pywin32 not available so COM fallback is skipped - "
                ".doc needs MS Word on Windows)".format(file_path, python_error)
            ) from python_error
        try:
            return _read_docx_com(file_path, with_tables)
        except WordFileNotFound:
            raise
        except Exception as com_error:
            raise WordBackendUnavailable(
                "Cannot read Word file: {} (python-docx: {}; COM: {})".format(file_path, python_error, com_error)
            ) from com_error