"""Đọc file Excel theo path và trả về dữ liệu JSON-serializable.

Dựa trên ``ExcelReaderSupport.py`` (script CLI gốc) nhưng viết lại theo chuẩn
thư viện của dự án: trả về dữ liệu / ném exception thay vì ``print(json)`` +
``sys.exit``, và có tầng backend thứ hai để không phụ thuộc MS Excel.

BACKEND
--------
1. openpyxl (mặc định) - thuần Python, chạy được headless / Linux / Docker.
2. win32com (fallback) - chỉ khi openpyxl đọc lỗi (file .xls cũ, file hỏng...)
   VÀ máy đang cài MS Excel (Windows). Cần ``pywin32``.

LƯU Ý
------
- ``read_only=True`` + ``data_only=True``: không nạp hết file vào RAM (file rất
  lớn vẫn OK) và lấy giá trị ĐÃ TÍNH của công thức - đúng hành vi của COM.
- ĐỌC CẢ SHEET ẨN (business cần xem hết dữ liệu, không bỏ qua sheet ẩn).
- File ``.xls`` (định dạng cũ) openpyxl KHÔNG đọc được -> rơi vào fallback COM
  => chỉ chạy được trên Windows có cài MS Excel. ``.xlsx`` / ``.xlsm`` thì ổn ở mọi nơi.
- Dữ liệu luôn JSON-safe: datetime -> ISO string, Decimal -> float, bytes -> str.
"""

import datetime as _dt
import logging
from decimal import Decimal

from libs.microsoft.office.errors import (
    ExcelBackendUnavailable,
    ExcelFileNotFound,
    ExcelSheetNotFound,
)

logger = logging.getLogger("apps")


def to_list(data):
    """Chuẩn hoá giá trị 2 chiều về list[list] (giữ nguyên logic file gốc).

    COM trả về tuple lồng nhau (hoặc scalar khi vùng dữ liệu chỉ có 1 ô), còn
    openpyxl trả list - hàm này gộp cả 2 về một kiểu duy nhất.
    """
    if data is None:
        return []
    # Chuoi (str/bytes) KHONG phai bang du lieu 2 chieu -> giu nguyen.
    if isinstance(data, (str, bytes, bytearray)):
        return [[data]]
    # COM tra tuple long nhau; openpyxl tra list HOAC GENERATOR
    # (iter_rows(values_only=True) -> generator) => dung moi iterable truoc,
    # KHONG kiem tra isinstance(tuple, list) vi se bo qua generator.
    if isinstance(data, (tuple, list, set, frozenset, range)) or hasattr(data, "__iter__"):
        rows = list(data)
    else:
        # Gia tri don (o Excel chi co 1 o) -> bo vao 1 hang
        return [[data]]
    result = []
    for row in rows:
        if isinstance(row, (str, bytes, bytearray)):
            result.append([row])
        elif isinstance(row, (tuple, list, set, frozenset, range)) or hasattr(row, "__iter__"):
            result.append(list(row))
        else:
            result.append([row])
    return result


def _jsonable(value):
    """Ép 1 ô về kiểu JSON-safe (datetime, Decimal, bytes, set...)."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    if isinstance(value, (set, frozenset, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (list, dict)):
        return [_jsonable(item) for item in value] if isinstance(value, list) else {
            str(k): _jsonable(v) for k, v in value.items()
        }
    return str(value)


def _is_blank(value):
    """True nếu ô trống (None hoặc chuỗi rỗng sau khi strip)."""
    if value is None:
        return True
    return isinstance(value, str) and value.strip() == ""


def rows_to_dicts(rows, header_row=1):
    """list[list] -> list[dict], key lấy từ tên cột ở ``header_row``.

    Ô header rỗng -> fallback ``col_1, col_2, ...`` (giữ hành vi file gốc) để
    dữ liệu không bị mất cột. Cột thiếu ở dòng dữ liệu -> None.
    """
    if not rows:
        return []
    header_index = max(0, int(header_row) - 1)
    if header_index >= len(rows):
        return []

    headers = []
    used_names = set()
    for col_index, raw_header in enumerate(rows[header_index]):
        name = raw_header if isinstance(raw_header, str) and raw_header.strip() else ""
        if not name:
            name = f"col_{col_index + 1}"
        # Tránh trùng key khi file có 2 cột cùng tên -> thêm hậu tố
        if name in used_names:
            suffix = 2
            while f"{name}_{suffix}" in used_names:
                suffix += 1
            name = f"{name}_{suffix}"
        used_names.add(name)
        headers.append(name)

    result = []
    for row in rows[header_index + 1 :]:
        if not row or all(_is_blank(cell) for cell in row):
            continue  # bỏ dòng trống hoàn toàn
        result.append(
            {
                headers[col_index]: (row[col_index] if col_index < len(row) else None)
                for col_index in range(len(headers))
            }
        )
    return result

# --- merge cell ---

# Gioi han kich thuoc o lon: Excel cho phep merge ca cot rong (vd ca cot Z) - neu
# duyet het se sinh hàng trieu o va treo. Chi duyet o nam trong khung du lieu thuc te.
MAX_MERGE_SPAN = 10000


def _used_bounds(rows):
    """Khung du lieu thuc te (max_row, max_col) cua list[list], bo qua o rong."""
    max_row = 0
    max_col = 0
    for row_index, row in enumerate(rows, start=1):
        if not row:
            continue
        for col_index, value in enumerate(row, start=1):
            if not _is_blank(value):
                if row_index > max_row:
                    max_row = row_index
                if col_index > max_col:
                    max_col = col_index
    return max_row, max_col


def _get_cell(rows, row_idx, col_idx):
    """Lay o theo toa do 1-based, tra None neu ngoai khung."""
    if row_idx < 1 or col_idx < 1 or row_idx > len(rows):
        return None
    row = rows[row_idx - 1]
    if not row or col_idx > len(row):
        return None
    return row[col_idx - 1]


def _set_cell(rows, row_idx, col_idx, value):
    """Gan o theo toa do 1-based, tu mo rong list neu thieu."""
    while len(rows) < row_idx:
        rows.append([])
    row = rows[row_idx - 1]
    while len(row) < col_idx:
        row.append(None)
    row[col_idx - 1] = value


def _build_merge_plan(ranges, max_row, max_col):
    """Chuyen danh sach vung merge thanh [(r1,c1,r2,c2), ...] co gioi han khung.

    ``ranges`` la iterable cua (min_col, min_row, max_col, max_row) - cung thu tu cho
    ca openpyxl va COM de khong phai phu thuoc thu vien nao.
    """
    plan = []
    for bounds in ranges:
        min_col, min_row, max_c, max_r = bounds
        # Cat ve khung du lieu thuc te: merge phia ngoai khung khong dua du lieu nao veo
        min_col = max(1, min_col)
        min_row = max(1, min_row)
        max_c = min(max_c, max_col)
        max_r = min(max_r, max_row)
        if max_c < min_col or max_r < min_row:
            continue
        # Dem o thuc te se duyet; vuot ngan can -> bo qua de tranh treo
        if (max_r - min_row + 1) * (max_c - min_col + 1) > MAX_MERGE_SPAN:
            continue
        plan.append((min_row, min_col, max_r, max_c))
    return plan


def _fill_merged_rows(rows, ranges):
    """Nhan ban gia tri goc xuong moi o trong vung merge.

    ``ranges`` iterable cua (min_col, min_row, max_col, max_row).

    Vì sao can xu ly MERGE CHONG NHAU (Excel cho phep): vung cha phai duoc xu ly
    truoc vung con, neu khong o con se nhan gia tri cua chinh no (None) thay vi gia
    tri goc cua cha. Thuat toan lap toi hoi tu: lap lai cho den khi khong con o nao
    thay doi.
    """
    max_row, max_col = _used_bounds(rows)
    plan = _build_merge_plan(ranges, max_row, max_col)
    if not plan:
        return rows

    for _ in range(len(plan) + 1):
        changed = False
        for min_row, min_col, max_r, max_c in plan:
            source = _get_cell(rows, min_row, min_col)
            if _is_blank(source):
                continue
            for row_idx in range(min_row, max_r + 1):
                for col_idx in range(min_col, max_c + 1):
                    if row_idx == min_row and col_idx == min_col:
                        continue
                    if _is_blank(_get_cell(rows, row_idx, col_idx)):
                        _set_cell(rows, row_idx, col_idx, source)
                        changed = True
        if not changed:
            break
    return rows

# --- backend 1: openpyxl (mac dinh) ---

def _safe_merged_labels(sheet):
    """Ten vung merge dang chuoi ('A1:B1').

    ReadOnlyWorksheet KHONG co ``merged_cells`` (chi co o che do read_only=False),
    nen luon tra list rong thay vi de AttributeError lam roi doc file.
    """
    ranges = getattr(sheet, "merged_cells", None)
    if ranges is None:
        return []
    return sorted(str(merged) for merged in ranges.ranges)


def _safe_merged_ranges(sheet):
    """Vung merge theo toa do (min_col, min_row, max_col, max_row)."""
    from openpyxl.utils import range_boundaries

    ranges = getattr(sheet, "merged_cells", None)
    if ranges is None:
        return []
    result = []
    for merged in ranges.ranges:
        try:
            min_col, min_row, max_col, max_row = range_boundaries(str(merged))
        except ValueError:
            continue
        result.append((min_col, min_row, max_col, max_row))
    return result


def _read_all_openpyxl(file_path, fill_merged=True):
    """Doc tat ca sheet bang openpyxl -> list[dict] theo tung sheet.

    ``read_only=False`` bat buoc: ReadOnlyWorksheet khong expose ``merged_cells``
    nen khong doc duoc vung merge o che do do (xem docstring file nay).
    """
    from openpyxl import load_workbook

    workbook = load_workbook(file_path, read_only=False, data_only=True)
    try:
        # DOC CA SHEET AN: khong loc sheet_state, business can xem het du lieu.
        sheets = list(workbook.worksheets)
        result = []
        for sheet in sheets:
            rows = [[_jsonable(cell) for cell in row] for row in to_list(sheet.iter_rows(values_only=True))]
            merged_labels = _safe_merged_labels(sheet)
            if fill_merged and merged_labels:
                rows = _fill_merged_rows(rows, _safe_merged_ranges(sheet))
            result.append({"sheet": sheet.title, "merged_ranges": merged_labels, "rows": rows})
        return result
    finally:
        workbook.close()


def _read_one_openpyxl(file_path, sheet_name, fill_merged=True):
    """Doc 1 sheet cu theo ten bang openpyxl -> dict {sheet, merged_ranges, rows}.

    ``read_only=False`` bat buoc: ReadOnlyWorksheet khong expose ``merged_cells``.
    """
    from openpyxl import load_workbook

    workbook = load_workbook(file_path, read_only=False, data_only=True)
    try:
        if sheet_name not in workbook.sheetnames:
            raise ExcelSheetNotFound(f"Sheet not found: {sheet_name}")
        sheet = workbook[sheet_name]
        rows = [[_jsonable(cell) for cell in row] for row in to_list(sheet.iter_rows(values_only=True))]
        merged_labels = _safe_merged_labels(sheet)
        if fill_merged and merged_labels:
            rows = _fill_merged_rows(rows, _safe_merged_ranges(sheet))
        return {"sheet": sheet.title, "merged_ranges": merged_labels, "rows": rows}
    finally:
        workbook.close()

# --- backend 2: win32com (fallback, chi Windows + co MS Excel) ---

def _has_com():
    """True neu import duoc pywin32 tren may hien tai."""
    try:
        import win32com.client  # noqa: F401

        return True
    except ImportError:
        return False


def _com_sheet_merges(sheet):
    """Doc vung merge cua 1 sheet COM -> (ranges, labels).

    COM khong cho lay danh sach merge nhu openpyxl, phai quet UsedRange:
    moi o co ``MergeCells=True`` se tra Address cua vung merge chua no (o goc
    tren cung tra chinh no). Gom cac Address, loai trung, roi chuyen sang toa do
    (min_col, min_row, max_col, max_row).
    """
    used = sheet.UsedRange
    addresses = set()
    for cell in used.Cells:
        try:
            if cell.MergeCells:
                addresses.add(str(cell.MergeArea.Address(External=False)))
        except Exception:  # pragma: no cover - COM loi la truong hop hiem
            continue

    ranges = []
    labels = []
    for address in addresses:
        labels.append(address.replace("$", ""))
        min_col, min_row, max_col, max_row = _parse_a1_bounds(address)
        if min_col is None:
            continue
        ranges.append((min_col, min_row, max_col, max_row))
    return ranges, sorted(labels)


def _parse_a1_bounds(address):
    """'A1:B3' (co the co dau $) -> (min_col, min_row, max_col, max_row)."""
    try:
        from openpyxl.utils.cell import column_index_from_string, coordinate_to_tuple
    except ImportError:  # pragma: no cover - openpyxl la dependency bat buoc
        return None, None, None, None
    try:
        text = str(address).replace("$", "")
        if ":" in text:
            start, end = text.split(":", 1)
        else:
            start = end = text
        start_col, start_row = coordinate_to_tuple(start)
        end_col, end_row = coordinate_to_tuple(end)
    except (ValueError, TypeError):
        return None, None, None, None
    _ = column_index_from_string  # giữ import cho rõ ý nghĩa (A -> 1)
    return min(start_col, end_col), min(start_row, end_row), max(start_col, end_col), max(start_row, end_row)

def _read_all_com(file_path, fill_merged=True):
    """Doc tat ca sheet bang COM (Excel that) -> list[dict] theo tung sheet."""
    import win32com.client

    excel = None
    workbook = None
    try:
        excel = win32com.client.gencache.EnsureDispatch("Excel.Application")
        workbook = excel.Workbooks.Open(file_path, ReadOnly=True)
        sheets = workbook.Worksheets
        result = []
        for index in range(1, sheets.Count + 1):
            sheet = sheets.Item(index)
            rows = to_list(sheet.UsedRange.Value)
            rows = [[_jsonable(cell) for cell in row] for row in rows]
            ranges, labels = _com_sheet_merges(sheet)
            if fill_merged and ranges:
                rows = _fill_merged_rows(rows, ranges)
            # DOC CA SHEET AN: khong kiem tra sheet.Visible
            result.append({"sheet": sheet.Name, "merged_ranges": labels, "rows": rows})
        return result
    finally:
        _close_com(workbook, excel)


def _read_one_com(file_path, sheet_name, fill_merged=True):
    """Doc 1 sheet cu theo ten bang COM (Excel that) -> dict {sheet, merged_ranges, rows}."""
    import win32com.client

    excel = None
    workbook = None
    try:
        excel = win32com.client.gencache.EnsureDispatch("Excel.Application")
        workbook = excel.Workbooks.Open(file_path, ReadOnly=True)
        names = [workbook.Worksheets.Item(i).Name for i in range(1, workbook.Worksheets.Count + 1)]
        if sheet_name not in names:
            raise ExcelSheetNotFound(f"Sheet not found: {sheet_name}")
        sheet = workbook.Worksheets.Item(sheet_name)
        rows = to_list(sheet.UsedRange.Value)
        rows = [[_jsonable(cell) for cell in row] for row in rows]
        ranges, labels = _com_sheet_merges(sheet)
        if fill_merged and ranges:
            rows = _fill_merged_rows(rows, ranges)
        return {"sheet": sheet.Name, "merged_ranges": labels, "rows": rows}
    finally:
        _close_com(workbook, excel)


def _close_com(workbook, excel):
    """Dong workbook + tat Excel (COM de lai process treu neu thieu cleanup)."""
    if workbook is not None:
        try:
            workbook.Close(False)
        except Exception:  # pragma: no cover - Excel co the da bi tat
            pass
    if excel is not None:
        try:
            excel.Quit()
        except Exception:  # pragma: no cover
            pass

# --- API cong khai ---

def read_excel(file_path, sheet=None, has_header=True, header_row=1, fill_merged=True):
    """Doc file Excel va tra ve du lieu JSON-serializable.

    Args:
        file_path (str): duong dan file Excel (.xlsx / .xlsm / .xls).
        sheet (str|None): ten sheet. ``None`` = doc TAT CA sheet (ke ca sheet an).
        has_header (bool): ``True`` -> moi sheet tra list[dict] theo ten cot;
            ``False`` -> tra list[list] nguyen ban.
        header_row (int): hang chua ten cot (1-based), chi dung khi ``has_header``.
        fill_merged (bool): ``True`` (mac dinh) nhan ban gia tri goc xuong moi o
            trong vung merge. ``False`` giu nguyen (o merge = None) - dung khi
            merge chi de bieu thi "o nay thuoc nhom" va ban can cao giu cao truc.

    Returns:
        ``sheet=None``   -> ``[{"sheet": str, "merged_ranges": [...], "rows": [...]}, ...]``
        ``sheet="S"``    -> ``{"sheet": "S", "merged_ranges": [...], "rows": [...]}``
        (rows = list[dict] neu has_header, nguoc lai list[list])

    Raises:
        ExcelFileNotFound: file khong ton tai.
        ExcelSheetNotFound: khong co sheet duoc chi dinh.
        ExcelBackendUnavailable: khong backend nao doc duoc.

    Vi du:
        >>> data = read_excel("D:/data/mau.xlsx")
        >>> rows = read_excel("D:/data/mau.xlsx", sheet="Sheet1")
        >>> raw = read_excel("D:/data/mau.xlsx", has_header=False)
        >>> keep = read_excel("D:/data/mau.xlsx", fill_merged=False)

    Merge cell:
        Excel chi gia tri vao o tren cung ben trai cua vung merge, con lai = None.
        Mac dinh ``fill_merged=True`` se nhan ban gia tri do xuong moi o trong vung
        de khong mat du lieu am tham (vi du cot gop doc file bao cao).
        ``merged_ranges`` luon duoc tra kem de truy vet vung da gop.
    """
    if not file_path:
        raise ExcelFileNotFound("Excel file path is required")
    try:
        exists = __import__("os").path.exists(file_path)
    except (OSError, ValueError) as error:
        raise ExcelFileNotFound(f"Invalid Excel file path: {file_path}") from error
    if not exists:
        raise ExcelFileNotFound(f"Excel file not found: {file_path}")

    try:
        if sheet is None:
            sheets_data = _read_all_openpyxl(file_path, fill_merged)
        else:
            sheets_data = [_read_one_openpyxl(file_path, sheet, fill_merged)]
    except ExcelSheetNotFound:
        raise
    except Exception as openpyxl_error:
        logger.warning(
            "openpyxl failed to read %s (%s) - trying COM fallback",
            file_path,
            openpyxl_error,
        )
        if not _has_com():
            raise ExcelBackendUnavailable(
                f"Cannot read Excel file: {file_path} "
                f"(openpyxl failed: {openpyxl_error}; pywin32 not available "
                f"so COM fallback is skipped - .xls needs MS Excel on Windows)"
            ) from openpyxl_error
        try:
            if sheet is None:
                sheets_data = _read_all_com(file_path, fill_merged)
            else:
                sheets_data = [_read_one_com(file_path, sheet, fill_merged)]
        except ExcelSheetNotFound:
            raise
        except Exception as com_error:
            raise ExcelBackendUnavailable(
                f"Cannot read Excel file: {file_path} "
                f"(openpyxl: {openpyxl_error}; COM: {com_error})"
            ) from com_error

    if has_header:
        for item in sheets_data:
            item["rows"] = rows_to_dicts(item["rows"], header_row=header_row)

    # Chi dinh 1 sheet -> tra THANG dict cua sheet do (khong boc trong list)
    if sheet is not None:
        return sheets_data[0]
    return sheets_data