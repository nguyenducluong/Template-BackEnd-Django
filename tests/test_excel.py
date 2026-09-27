"""Test libs.microsoft.office.

T\u1ea1o file .xlsx TH\u1eadT b\u1eb1ng openpyxl trong tmp_path \u21d2 KH\u00d4NG c\u1ea7n c\u00e0i MS Excel,
test ch\u1ea1y \u0111\u01b0\u1ee3c tr\u00ean m\u00e1y dev / CI Linux.
"""

import datetime

import pytest
from openpyxl import Workbook

from libs.microsoft.office import (
    ExcelBackendUnavailable,
    ExcelFileNotFound,
    ExcelSheetNotFound,
    read_excel,
)


def _make_xlsx(path, sheets):
    """T\u1ea1o file xlsx t\u1eeb dict {ten_sheet: [[o], [hang...]]}."""
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(title=name)
        for row in rows:
            ws.append(row)
    wb.save(str(path))
    return str(path)

# ---------------------------------------------------------------- to_list ---


class TestToList:
    def test_none_returns_empty(self):
        from libs.microsoft.office.reader import to_list

        assert to_list(None) == []

    def test_scalar_wrapped_in_row(self):
        from libs.microsoft.office.reader import to_list

        assert to_list(5) == [[5]]

    def test_flat_list_each_becomes_row(self):
        from libs.microsoft.office.reader import to_list

        assert to_list([1, 2, 3]) == [[1], [2], [3]]

    def test_nested_tuple_converted(self):
        from libs.microsoft.office.reader import to_list

        assert to_list(((1, 2), (3, 4))) == [[1, 2], [3, 4]]


# ------------------------------------------------------------ read_excel ---


class TestReadExcel:
    def test_reads_all_sheets_as_list_of_dicts(self, tmp_path):
        path = _make_xlsx(
            tmp_path / "a.xlsx",
            {
                "Sheet1": [["code", "name"], ["A1", "Alpha"]],
                "Sheet2": [["code", "name"], ["B1", "Beta"]],
            },
        )
        data = read_excel(path)
        assert len(data) == 2
        assert data[0]["sheet"] == "Sheet1"
        assert data[0]["rows"] == [{"code": "A1", "name": "Alpha"}]
        assert data[1]["rows"] == [{"code": "B1", "name": "Beta"}]

    def test_reads_hidden_sheets_too(self, tmp_path):
        """Y \u0111\u00e3 ch\u00e0m: \u0111\u1ecdc C\u1ea3 sheet \u1e9bn, kh\u00f4ng b\u1ecf qua."""
        path = tmp_path / "h.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "Visible"
        ws.append(["code"])
        ws.append(["V1"])
        hidden = wb.create_sheet("Hidden")
        hidden.append(["code"])
        hidden.append(["H1"])
        hidden.sheet_state = "hidden"
        wb.save(str(path))

        names = [item["sheet"] for item in read_excel(str(path))]
        assert "Visible" in names
        assert "Hidden" in names, "sheet \u1e9bn ph\u1ea3i \u0111\u01b0\u1ee3c \u0111\u1ecdc"
        hidden_data = next(i for i in read_excel(str(path)) if i["sheet"] == "Hidden")
        assert hidden_data["rows"] == [{"code": "H1"}]

    def test_single_sheet_returns_dict(self, tmp_path):
        """Chi dinh sheet -> tra THANG dict {sheet, merged_ranges, rows}."""
        path = _make_xlsx(tmp_path / "b.xlsx", {"S": [["code"], ["A1"]]})
        result = read_excel(path, sheet="S")
        assert result["sheet"] == "S"
        assert result["rows"] == [{"code": "A1"}]
        assert result["merged_ranges"] == []

    def test_without_header_returns_list_of_lists(self, tmp_path):
        path = _make_xlsx(tmp_path / "c.xlsx", {"S": [["code", "name"], ["A1", "Alpha"]]})
        data = read_excel(path, has_header=False)
        assert data[0]["rows"] == [["code", "name"], ["A1", "Alpha"]]

    def test_header_row_option(self, tmp_path):
        path = _make_xlsx(tmp_path / "d.xlsx", {"S": [["junk"], ["code", "name"], ["A1", "Alpha"]]})
        data = read_excel(path, header_row=2)
        assert data[0]["rows"] == [{"code": "A1", "name": "Alpha"}]

    def test_blank_header_falls_back_to_col_index(self, tmp_path):
        path = _make_xlsx(tmp_path / "e.xlsx", {"S": [["code", "", "name"], ["A1", "mid", "Alpha"]]})
        data = read_excel(path)
        assert data[0]["rows"] == [{"code": "A1", "col_2": "mid", "name": "Alpha"}]

    def test_duplicate_header_names_get_suffixed(self, tmp_path):
        path = _make_xlsx(tmp_path / "f.xlsx", {"S": [["code", "code"], ["A1", "A2"]]})
        data = read_excel(path)
        assert data[0]["rows"] == [{"code": "A1", "code_2": "A2"}]

    def test_fully_empty_rows_skipped(self, tmp_path):
        path = _make_xlsx(tmp_path / "g.xlsx", {"S": [["code"], ["A1"], [None], ["A2"]]})
        data = read_excel(path)
        assert data[0]["rows"] == [{"code": "A1"}, {"code": "A2"}]

    def test_datetime_converted_to_iso_string(self, tmp_path):
        path = _make_xlsx(tmp_path / "h.xlsx", {"S": [["d"], [datetime.datetime(2025, 12, 1, 10, 30)]]})
        data = read_excel(path)
        assert data[0]["rows"][0]["d"].startswith("2025-12-01T10:30")

# --------------------------------------------------------------- errors ---


class TestErrors:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ExcelFileNotFound):
            read_excel(str(tmp_path / "khong-ton-tai.xlsx"))

    def test_missing_sheet_raises(self, tmp_path):
        path = _make_xlsx(tmp_path / "i.xlsx", {"S": [["code"], ["A1"]]})
        with pytest.raises(ExcelSheetNotFound):
            read_excel(path, sheet="KhongCo")

    def test_broken_file_raises_backend_unavailable(self, tmp_path):
        """File .xlsx sai dinh dang + khong co COM -> ExcelBackendUnavailable."""
        bad = tmp_path / "bad.xlsx"
        bad.write_text("khong phai file excel")
        with pytest.raises(ExcelBackendUnavailable):
            read_excel(str(bad))


# ------------------------------------------------------ COM fallback path ---


class TestComFallback:
    def test_falls_back_to_com_when_openpyxl_fails(self, tmp_path, monkeypatch):
        """openpyxl hong -> phai co gang COM (khong spawn Excel that)."""
        import libs.microsoft.office.reader as reader

        called = {}

        def boom(*_args, **_kwargs):
            raise ValueError("openpyxl broken")

        def fake_has_com():
            return True

        def fake_read_all_com(_file_path, _fill_merged=True):
            called["com"] = True
            return [{"sheet": "S", "merged_ranges": [], "rows": [["code"], ["A1"]]}]

        monkeypatch.setattr(reader, "_read_all_openpyxl", boom)
        monkeypatch.setattr(reader, "_has_com", fake_has_com)
        monkeypatch.setattr(reader, "_read_all_com", fake_read_all_com)

        # File phai TON TAI that (read_excel kiem tra path truoc khi goi backend)
        path = _make_xlsx(tmp_path / "x.xlsx", {"S": [["code"], ["A1"]]})
        data = reader.read_excel(path)
        assert called.get("com") is True, "phai co goi fallback COM"
        assert data[0]["rows"] == [{"code": "A1"}]

    def test_raises_backend_unavailable_when_no_com(self, tmp_path, monkeypatch):
        """openpyxl hong + khong co COM -> nem ExcelBackendUnavailable."""
        import libs.microsoft.office.reader as reader

        monkeypatch.setattr(
            reader,
            "_read_all_openpyxl",
            lambda *_a, **_k: (_ for _ in ()).throw(ValueError("openpyxl broken")),
        )
        monkeypatch.setattr(reader, "_has_com", lambda: False)
        path = _make_xlsx(tmp_path / "y.xlsx", {"S": [["code"], ["A1"]]})
        with pytest.raises(ExcelBackendUnavailable):
            reader.read_excel(path)

# ------------------------------------------------------------- merge cell ---


def _make_merged_xlsx(path):
    """File co merge ngang o header (A1:B1) va merge doc o du lieu (A2:A3)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "S"
    ws["A1"] = "Ma"
    ws["B1"] = None
    ws["C1"] = "Ten"
    ws.merge_cells("A1:B1")
    ws["A2"] = "A1"
    ws["C2"] = "Alpha"
    ws["A3"] = "A2"
    ws["C3"] = "Beta"
    ws.merge_cells("A2:A3")
    wb.save(str(path))
    return str(path)


class TestFillMerged:
    def test_merged_ranges_reported(self, tmp_path):
        path = _make_merged_xlsx(tmp_path / "m.xlsx")
        data = read_excel(path)
        assert sorted(data[0]["merged_ranges"]) == ["A1:B1", "A2:A3"]

    def test_vertical_merge_fills_down(self, tmp_path):
        """A2:A3 merge -> ca 2 dong deu phai nhan 'A1' (khong mat du lieu)."""
        path = _make_merged_xlsx(tmp_path / "m2.xlsx")
        rows = read_excel(path)[0]["rows"]
        # 2 dong duoc gop trong A2:A3 -> ca 2 deu nhan gia tri goc 'A1'
        assert [r["Ma"] for r in rows] == ["A1", "A1"]
        assert [r["Ten"] for r in rows] == ["Alpha", "Beta"]

    def test_horizontal_merge_in_header_fills_all_columns(self, tmp_path):
        """A1:B1 merge -> ca o A1 va B1 deu mang gia tri 'Ma' (khong con o rong).

        Key dict se trung ten -> rows_to_dicts tu them hau to (Ma / Ma_2);
        quan trong la: 2 o header deu CO gia tri, khong con cot rong (col_N).
        """
        path = _make_merged_xlsx(tmp_path / "m3.xlsx")
        # O B1 (trong vung merge A1:B1) phai duoc lap gia tri tu A1.
        # Ha qua: header B1 rong -> sinh ten cot 'col_2' rac; bat buoc co 'Ma_2'.
        item = read_excel(path)[0]
        row = item["rows"][0]
        assert "Ma_2" in row, "o B1 trong vung merge phai nhan gia tri cua o goc A1"
        assert not any(key.startswith("col_") for key in row), "khong duoc sinh cot rong rac"
        assert row["Ma"] == "A1"
        assert row["Ten"] == "Alpha"

    def test_fill_merged_false_keeps_none(self, tmp_path):
        """fill_merged=False -> giu hanh vi goc (o merge = None) nhung van co merged_ranges."""
        path = _make_merged_xlsx(tmp_path / "m4.xlsx")
        data = read_excel(path, fill_merged=False)
        rows = data[0]["rows"]
        assert rows[1]["Ma"] is None  # dong thu 2 cua A2:A3
        assert data[0]["merged_ranges"] == ["A1:B1", "A2:A3"]

    def test_no_merged_ranges_key_when_empty(self, tmp_path):
        path = _make_xlsx(tmp_path / "nm.xlsx", {"S": [["code"], ["A1"]]})
        assert read_excel(path)[0]["merged_ranges"] == []

class TestFillMergedEdgeCases:
    def test_nested_merge_uses_parent_value(self, tmp_path):
        """Merge chong nhau: vung cha A1:A3, vung con A2:A3 -> ca 3 deu nhan gia tri cha."""
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "S"
        ws["A1"] = "Goc"
        ws["B1"] = "Ten"
        ws["A2"] = None
        ws["A3"] = None
        ws["B2"] = "X"
        ws["B3"] = "Y"
        ws.merge_cells("A1:A3")
        ws.merge_cells("A2:A3")
        path = str(tmp_path / "nested.xlsx")
        wb.save(path)

        rows = read_excel(path)[0]["rows"]
        assert [r["Goc"] for r in rows] == ["Goc", "Goc"]

    def test_merge_larger_than_max_span_is_skipped(self, tmp_path):
        """Vung merge vuot MAX_MERGE_SPAN phai BO QUA (khong duyet hang trieu o).

        Dung muc vua du kien _build_merge_plan cat (10001 o) thay vi 1e6 de test
        chay nhanh - openpyxl mat ~10s chi de TAO file merge 1e6 dong.
        """
        from libs.microsoft.office.reader import MAX_MERGE_SPAN, _build_merge_plan

        # Vung vuot MAX_MERGE_SPAN NHUNG nam trong khung du lieu -> phai bo qua
        huge = (1, 1, 1, MAX_MERGE_SPAN + 1000)
        plan = _build_merge_plan([huge], max_row=MAX_MERGE_SPAN + 1000, max_col=1)
        assert plan == [], "vung merge vuot MAX_MERGE_SPAN phai bi bo qua"

        # Vung vuot khung du lieu -> cat ve khung (chi con 2 o) va van xu ly duoc
        trimmed = _build_merge_plan([huge], max_row=2, max_col=2)
        assert trimmed == [(1, 1, 2, 1)], "vung vuot khung phai duoc cat ve khung du lieu"

    def test_merge_outside_data_range_is_trimmed(self, tmp_path):
        """Merge vuot khung du lieu -> chi giu phan nam trong khung."""
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "S"
        ws["A1"] = "Ma"
        ws["B1"] = "Ten"
        ws["A2"] = "A1"
        ws["B2"] = "Alpha"
        ws.merge_cells("A1:A50")  # vuot khung du lieu thuc te (2 dong)
        path = str(tmp_path / "trim.xlsx")
        wb.save(path)

        item = read_excel(path)[0]
        assert item["merged_ranges"] == ["A1:A50"]
        # Chi dong 1-2 nam trong vung -> ca 2 deu nhan gia tri
        assert item["rows"] == [{"Ma": "Ma", "Ten": "Alpha"}]

    def test_merged_ranges_empty_list_for_sheet_without_merge(self, tmp_path):
        path = _make_xlsx(tmp_path / "plain.xlsx", {"S": [["code"], ["A1"]]})
        assert read_excel(path)[0]["merged_ranges"] == []

    def test_single_sheet_dict_has_merged_ranges(self, tmp_path):
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "S"
        ws["A1"] = "Ma"
        ws["A2"] = "A1"
        ws["B1"] = "Ten"
        ws["B2"] = "Alpha"
        ws.merge_cells("A1:B1")
        path = str(tmp_path / "one.xlsx")
        wb.save(path)

        result = read_excel(path, sheet="S")
        assert result["merged_ranges"] == ["A1:B1"]