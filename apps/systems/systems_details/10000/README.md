# Header 10000 — Demo (tiếng Việt, không translator, không cần DB/quyền)

Header demo chạy qua dispatcher `POST /api/v1/systems/init_data`
`{header_id: 10000, func, params}` — chỉ cần đăng nhập, không cần
`SystemHeader` / `HeaderRegistration` / `SystemPower` trong DB
(dispatcher + `HasHeaderPermission` bypass header demo).

## Cách gọi thử API

```bash
# details full (lần đầu mở header)
POST /api/v1/systems/init_data  {header_id: 10000, func: "details", params: {scope: "full"}}
# search + phân trang + lọc
POST /api/v1/systems/init_data  {header_id: 10000, func: "search", params: {query: {limit: 2, offset: 0, details: {vendorCode: "DK"}}}}
# submit demo (echo, không lưu DB)
POST /api/v1/systems/init_data  {header_id: 10000, func: "submit_form", params: {header_id: 10000, dialog_id: "dlg_input_system", action_id: "dlg_input_system.save", power_key: 1, values: {vendor_code: "DK01"}}}
```

## Muốn tạo header thật mới từ demo này

1. Copy thư mục `10000` → `{N}`, đổi `HEADER_ID`, tên class `Header10000*` → `Header{N}*`, `header_id`, `pk`.
2. Sửa text tiếng Việt trực tiếp trong `payload.py` (cần đa ngôn ngữ mới dùng marker `@` + `translations.py`).
3. Tạo `SystemHeader id={N}` trong DB + đăng ký quyền (HeaderRegistration / UserHeaderRegistration).
4. Dispatcher `systems/init_data` tự nhận qua `import_module(...{N}.views)` (header thật không thuộc diện bypass demo).

