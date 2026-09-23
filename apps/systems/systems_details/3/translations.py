"""
Translation UI của Header 1 — Waiting for IQC (입고검사대상 및 결과입력).

Key đặt theo đường dẫn trong payload (payload dùng marker "@key" cho các chuỗi này).
Ngôn ngữ hỗ trợ: vi / en / kr — khớp Accept-Language frontend (app.slice language).
"""

TRANSLATIONS = {
	# ---- Search labels ----
	"search.labels.org": {"vi": "Bộ phận", "en": "Department", "kr": "부서"},
	"search.labels.period": {"vi": "Thời gian", "en": "Period", "kr": "기간"},
	"search.labels.details": {"vi": "Chi tiết", "en": "Details", "kr": "상세"},
	"search.labels.search": {"vi": "Tìm kiếm", "en": "Search", "kr": "검색"},
	# ---- Search views (tab Org/Period/Details) ----
	"search.views.org.label": {"vi": "Bộ phận", "en": "Department", "kr": "부서"},
	"search.views.period.label": {"vi": "Thời gian", "en": "Period", "kr": "기간"},
	"search.views.details.label": {"vi": "Chi tiết", "en": "Details", "kr": "상세"},
	# ---- Search fields (tên field tìm kiếm động) ----
	"search.fields.multi_status.name": {"vi": "Multi Select", "en": "Multi Select", "kr": "멀티 선택"},
	"search.fields.status.name": {"vi": "Select", "en": "Select", "kr": "선택"},
	"search.fields.gen_id.name": {"vi": "Mã nhân viên", "en": "Employee ID", "kr": "사원 코드"},
	"search.fields.key_shift.name": {"vi": "Ca làm việc", "en": "Work Shift", "kr": "교대 근무"},
	"search.fields.gender.name": {"vi": "Giới tính", "en": "Gender", "kr": "성별"},
	# ---- Table layout titles ----
	"table.layout.kpi.title": {
		"vi": "Bảng KPI Data (Hiển thị số Lot PASS FAIL... hoặc hiện số lượng)",
		"en": "KPI Data Table (Shows PASS/FAIL Lot counts or quantities)",
		"kr": "KPI 데이터 테이블 (PASS/FAIL Lot 수량 표시)",
	},
	"table.layout.grouped.title": {
		"vi": "Bảng sử dụng cho grouped có gộp dòng dữ liệu",
		"en": "Grouped table with merged data rows",
		"kr": "데이터 행 병합 grouped 테이블",
	},
	"table.layout.data.title": {
		"vi": "Danh sách Master Vendor",
		"en": "Master Vendor List",
		"kr": "Master Vendor 목록",
	},
	# ---- Table power actions ----
	"table.power_actions.1.label": {"vi": "Nhập dữ liệu hệ thống", "en": "Enter system data", "kr": "시스템 데이터 입력"},
	# ---- Dialog dlg_input_system ----
	"dialog.dlg_input_system.header.label": {"vi": "Tiêu đề dialog", "en": "Dialog title", "kr": "다이얼로그 제목"},
	"dialog.dlg_input_system.sections.0.label": {
		"vi": "Chi tiết có 2,3,4 cột",
		"en": "Details with 2,3,4 columns",
		"kr": "2,3,4열 상세",
	},
	"dialog.dlg_input_system.sections.1.label": {"vi": "Tệp đính kèm", "en": "Attachments", "kr": "첨부 파일"},
	"dialog.dlg_input_system.actions.0.label": {"vi": "Hủy bỏ", "en": "Cancel", "kr": "취소"},
	"dialog.dlg_input_system.actions.1.label": {"vi": "Lưu", "en": "Save", "kr": "저장"},
	"dialog.dlg_input_system.actions.1.confirmation.title": {
		"vi": "Xác nhận lưu",
		"en": "Confirm save",
		"kr": "저장 확인",
	},
	"dialog.dlg_input_system.actions.1.confirmation.message": {
		"vi": "Bạn có chắc chắn muốn lưu thay đổi?",
		"en": "Are you sure you want to save the changes?",
		"kr": "변경 사항을 저장하시겠습니까?",
	},
	"dialog.dlg_input_system.actions.1.confirmation.confirmLabel": {"vi": "Đồng ý", "en": "Confirm", "kr": "확인"},
	"dialog.dlg_input_system.actions.1.confirmation.cancelLabel": {"vi": "Hủy", "en": "Cancel", "kr": "취소"},
}
