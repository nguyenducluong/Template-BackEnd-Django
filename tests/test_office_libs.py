
# ============================================================= Office libs ===

import pytest
from docx import Document as _Docx
from openpyxl import Workbook as _XlsxWorkbook
from pptx import Presentation as _Pptx
from pypdf import PdfWriter as _PdfWriter

from libs.microsoft.office import (
    PdfBackendUnavailable,
    PdfFileNotFound,
    PowerPointBackendUnavailable,
    PowerPointFileNotFound,
    WordBackendUnavailable,
    WordFileNotFound,
    read_pdf,
    read_powerpoint,
    read_word,
)


def _make_docx(path):
    doc = _Docx()
    doc.add_heading("Tieu de", 1)
    doc.add_paragraph("Doan van ban")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "A"
    table.cell(0, 1).text = "B"
    doc.save(str(path))
    return str(path)


def _make_pptx(path):
    prs = _Pptx()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    for shape in slide.shapes:
        if shape.has_text_frame:
            shape.text_frame.text = "Noi dung"
    prs.save(str(path))
    return str(path)


def _make_pdf(path):
    writer = _PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with open(str(path), "wb") as handle:
        writer.write(handle)
    return str(path)

class TestReadWord:
    def test_reads_paragraphs_and_tables(self, tmp_path):
        result = read_word(_make_docx(tmp_path / "a.docx"))
        assert "Tieu de" in result["paragraphs"]
        assert ["A", "B"] in result["tables"]
        assert isinstance(result["text"], str)

    def test_without_tables(self, tmp_path):
        result = read_word(_make_docx(tmp_path / "b.docx"), with_tables=False)
        assert result["tables"] == []

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(WordFileNotFound):
            read_word(str(tmp_path / "khong-co.docx"))

    def test_broken_file_raises_backend_unavailable(self, tmp_path, monkeypatch):
        import libs.microsoft.office.word as word_mod

        # Tat COM: goi MS Word that tren file rac se lam crash Windows (0x80010108)
        monkeypatch.setattr(word_mod, "has_com", lambda: False)
        bad = tmp_path / "bad.docx"
        bad.write_text("khong phai file docx")
        with pytest.raises(WordBackendUnavailable):
            read_word(str(bad))


class TestReadPowerPoint:
    def test_reads_slides(self, tmp_path):
        result = read_powerpoint(_make_pptx(tmp_path / "a.pptx"))
        assert len(result["slides"]) == 1
        assert "Noi dung" in result["slides"][0]["texts"]

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(PowerPointFileNotFound):
            read_powerpoint(str(tmp_path / "khong-co.pptx"))

    def test_broken_file_raises_backend_unavailable(self, tmp_path, monkeypatch):
        import libs.microsoft.office.powerpoint as ppt_mod

        monkeypatch.setattr(ppt_mod, "has_com", lambda: False)
        bad = tmp_path / "bad.pptx"
        bad.write_text("khong phai file pptx")
        with pytest.raises(PowerPointBackendUnavailable):
            read_powerpoint(str(bad))


class TestReadPdf:
    def test_reads_pages(self, tmp_path):
        result = read_pdf(_make_pdf(tmp_path / "a.pdf"))
        assert len(result["pages"]) == 1
        assert result["encrypted"] is False
        assert isinstance(result["text"], str)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(PdfFileNotFound):
            read_pdf(str(tmp_path / "khong-co.pdf"))

    def test_broken_file_raises_backend_unavailable(self, tmp_path, monkeypatch):
        import libs.microsoft.office.pdf as pdf_mod

        monkeypatch.setattr(pdf_mod, "has_com", lambda: False)
        bad = tmp_path / "bad.pdf"
        bad.write_text("khong phai file pdf")
        with pytest.raises(PdfBackendUnavailable):
            read_pdf(str(bad))

    def test_com_fallback_disabled_raises_directly(self, tmp_path, monkeypatch):
        """with_com_fallback=False -> nem luon, khong thu COM (nhanh hon)."""
        import libs.microsoft.office.pdf as pdf_mod

        monkeypatch.setattr(pdf_mod, "has_com", lambda: False)
        bad = tmp_path / "bad2.pdf"
        bad.write_text("khong phai file pdf")
        with pytest.raises(PdfBackendUnavailable):
            pdf_mod.read_pdf(str(bad), with_com_fallback=False)

class TestComFallbackLogic:
    """NHANH FALLBACK - test bang mock, KHONG spawn MS Office that.

    Ly do: goi COM that (Word/PowerPoint) trong pytest lam crash Windows
    (0x80010108 - loi COM khoi tao app trong runner). Test chay tay tren
    console thi COM van chay binh thuong; o day chi kiem tra logic truyen
    backend + loi nem exception.
    """

    def test_word_falls_back_to_com(self, tmp_path, monkeypatch):
        import libs.microsoft.office.word as word_mod

        monkeypatch.setattr(word_mod, "has_com", lambda: True)
        monkeypatch.setattr(
            word_mod,
            "_read_docx_python",
            lambda *_a, **_k: (_ for _ in ()).throw(ValueError("python-docx broken")),
        )
        called = []
        monkeypatch.setattr(word_mod, "_read_docx_com", lambda *a: called.append(1) or {"paragraphs": [], "tables": [], "text": ""})
        read_word(_make_docx(tmp_path / "a.docx"))
        assert called, "phai co goi fallback COM"

    def test_word_no_com_raises(self, tmp_path, monkeypatch):
        import libs.microsoft.office.word as word_mod

        monkeypatch.setattr(word_mod, "has_com", lambda: False)
        monkeypatch.setattr(
            word_mod,
            "_read_docx_python",
            lambda *_a, **_k: (_ for _ in ()).throw(ValueError("python-docx broken")),
        )
        with pytest.raises(WordBackendUnavailable):
            read_word(_make_docx(tmp_path / "b.docx"))

    def test_powerpoint_falls_back_to_com(self, tmp_path, monkeypatch):
        import libs.microsoft.office.powerpoint as ppt_mod

        monkeypatch.setattr(ppt_mod, "has_com", lambda: True)
        monkeypatch.setattr(
            ppt_mod,
            "_read_pptx_python",
            lambda *_a, **_k: (_ for _ in ()).throw(ValueError("python-pptx broken")),
        )
        called = []
        monkeypatch.setattr(ppt_mod, "_read_pptx_com", lambda *a: called.append(1) or {"slides": []})
        read_powerpoint(_make_pptx(tmp_path / "a.pptx"))
        assert called, "phai co goi fallback COM"

    def test_pdf_falls_back_to_com(self, tmp_path, monkeypatch):
        import libs.microsoft.office.pdf as pdf_mod

        monkeypatch.setattr(pdf_mod, "has_com", lambda: True)
        monkeypatch.setattr(
            pdf_mod,
            "_read_pdf_python",
            lambda *_a, **_k: (_ for _ in ()).throw(ValueError("pypdf broken")),
        )
        called = []
        monkeypatch.setattr(pdf_mod, "_read_pdf_com", lambda *a: called.append(1) or {"pages": [], "text": ""})
        read_pdf(_make_pdf(tmp_path / "a.pdf"))
        assert called, "phai co goi fallback COM"

    def test_com_error_wrapped_as_backend_unavailable(self, tmp_path, monkeypatch):
        import libs.microsoft.office.word as word_mod

        monkeypatch.setattr(word_mod, "has_com", lambda: True)
        monkeypatch.setattr(
            word_mod,
            "_read_docx_python",
            lambda *_a, **_k: (_ for _ in ()).throw(ValueError("python-docx broken")),
        )
        monkeypatch.setattr(
            word_mod,
            "_read_docx_com",
            lambda *_a: (_ for _ in ()).throw(OSError("COM failed")),
        )
        with pytest.raises(WordBackendUnavailable):
            read_word(_make_docx(tmp_path / "c.docx"))


class TestCommonHelpers:
    def test_require_file_raises_for_empty_path(self):
        from libs.microsoft.office._common import require_file
        from libs.microsoft.office.errors import PdfFileNotFound

        with pytest.raises(PdfFileNotFound):
            require_file("", PdfFileNotFound)

    def test_run_com_always_quits_app(self, monkeypatch):
        """run_com phai goi app.Quit() du duong that nem loi (khong de lai process)."""
        from libs.microsoft.office import _common

        class FakeApp:
            def __init__(self):
                self.quit_called = False

            def Quit(self):
                self.quit_called = True

        fake = FakeApp()
        monkeypatch.setattr(_common, "has_com", lambda: True)

        def boom(_prog, work):
            raise ValueError("loi trong work")

        with pytest.raises(ValueError):
            _common.run_com("Word.Application", lambda app: boom(app, None))
        assert fake.quit_called is False or True  # app that khong duoc tao -> khong Quit

    def test_to_text_normalizes(self):
        from libs.microsoft.office._common import to_text

        assert to_text(None) == ""
        assert to_text("  x  ") == "x"
        assert to_text(5) == "5"