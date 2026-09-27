# -*- coding: utf-8 -*-
"""Tien ich dung chung cho cac backend doc file trong libs.microsoft.office.

Tach rieng de reader.py / word.py / powerpoint.py / pdf.py khong lap lai
3 phan: kiem tra file ton tai, chay COM co finally, xac dinh backend fallback.
"""

import logging
import os

from libs.microsoft.office.errors import ExcelFileNotFound  # noqa: F401  (re-export tien)

logger = logging.getLogger("apps")


def require_file(file_path, err_cls):
    """Kiem tra file ton tai, nem *err_cls* neu sai.

    Args:
        file_path: duong dan can kiem tra.
        err_cls: exception class se nem (ExcelFileNotFound / DocxFileNotFound...).

    Raises:
        err_cls: khi rong, khong ton tai, hoac khong doc duoc theo duong dan.
    """
    if not file_path:
        raise err_cls("File path is required")
    try:
        exists = os.path.exists(file_path)
    except (OSError, ValueError) as error:
        raise err_cls("Invalid file path: {}".format(file_path)) from error
    if not exists:
        raise err_cls("File not found: {}".format(file_path))


def has_com():
    """True neu import duoc pywin32 tren may hien tai (Windows + cai pywin32)."""
    try:
        import win32com.client  # noqa: F401

        return True
    except ImportError:
        return False


def run_com(app_prog_id, work):
    """Mo mot ung dung Office bang COM, chay *work*(app), luon tat app sau khi xong.

    Args:
        app_prog_id: ten COM app ("Word.Application", "PowerPoint.Application").
        work: callable nhan app, tra ve ket qua can dung.

    Returns:
        Gia tri tra ve cua *work*.

    Raises:
        Exception: loi tu Excel/pywin32 trong *work* hoac tu chinh viec mo app.
    """
    import win32com.client

    app = None
    try:
        app = win32com.client.gencache.EnsureDispatch(app_prog_id)
        return work(app)
    finally:
        # Luon tat app: khong release thi Excel/Word/PowerPoint treo lai trong
        # Task Manager va giu file dang mo (file bi khoa, khong xoa/ghi duoc).
        if app is not None:
            try:
                app.Quit()
            except Exception:  # pragma: no cover - app co the da bi tat truoc do
                pass


def to_text(value):
    """Chuan hoa gia tri o doc ve str (None -> '')."""
    if value is None:
        return ""
    return str(value).strip()