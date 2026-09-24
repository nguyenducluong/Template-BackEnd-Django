"""
Payload chi tiết của Header 1 — Waiting for IQC (입고검사대상 및 결과입력).

Port từ STD/src/redux/systemSlice/detailsSlice/example/_1.jsx sang Python dict.
Cấu trúc: { config, data, initial_state } — đúng blueprint frontend render.
"""

HEADER_ID = 1

DETAILS = {
	"config": {
		# Giá trị mặc định cho FE — FE đọc từ response `init_data` (không hardcode):
		# endpoint của dispatcher `apps.systems.views.SystemDispatchView` + tên func.
		"defaults": {
			"endpoint": "systems/init_data",
			"funcs": {
				"details": "details",
				"search": "search",
				"submit": "submit_form",
				"action": "action",
			},
		},
		"search": {
			"labels": {
				"org": "@search.labels.org",
				"period": "@search.labels.period",
				"details": "@search.labels.details",
				"search": "@search.labels.search",
			},
			"views": [
				{"id": "org", "component": "OrgView", "show": True, "label": "@search.views.org.label"},
				{"id": "period", "component": "PeriodView", "show": True, "label": "@search.views.period.label"},
				{"id": "details", "component": "DetailView", "show": True, "label": "@search.views.details.label"},
			],
			"period_config": {
				"minDate": "1980-01-01",
				"maxDate": "2030-12-31",
				"defaultFrom": "2025-12-01",
				"defaultTo": "2025-12-14",
			},
			"fields": [
				{"key": "multi_status", "name": "@search.fields.multi_status.name", "type": "multiselect"},
				{"key": "status", "name": "@search.fields.status.name", "type": "select"},
				{"key": "gen_id", "name": "@search.fields.gen_id.name", "type": "text", "regex": "/[^0-9]/g", "max_length": 8},
				{"key": "key_shift", "name": "@search.fields.key_shift.name", "type": "checkbox"},
				{"key": "gender", "name": "@search.fields.gender.name", "type": "radio"},
			],
		},
		"table": {
			"layouts": [
				# ─── TABLE 1: KPI Table ───
				{
					"type": "table_kpi",
					"title": "@table.layout.kpi.title",
					"data_key": "kpi_table_data",
					"config": {
						"col_keys": [
							{"col_w": 60, "key": "stt", "level": 1},
							{"col_w": 320, "key": "col1", "level": 1},
							{"col_w": 320, "key": "col2", "level": 1},
							{"col_w": 320, "key": "col3", "level": 2},
							{"col_w": 320, "key": "col4", "level": 1},
							{"col_w": 320, "key": "col5", "level": 2},
							{"col_w": 320, "key": "col6", "level": 3},
							{"col_w": 320, "key": "col7", "level": 3},
						],
						"headers": [
							{"title": "@table.headers.stt"}, {"title": "@table.kpi.headers.col1"}, {"title": "@table.kpi.headers.col2"}, {"title": "@table.kpi.headers.col3"},
							{"title": "@table.kpi.headers.col4"}, {"title": "@table.kpi.headers.col5"}, {"title": "@table.kpi.headers.col6"}, {"title": "@table.kpi.headers.col7"},
						],
						"hierarchyKeys": ["subGroups", "details"],
					},
				},
				# ─── TABLE 2: Grouped Table (Gộp dòng) ───
				{
					"type": "table_grouped",
					"title": "@table.layout.grouped.title",
					"data_key": "defect_overall",
					"config": {
						"tabs": ["@table.grouped.tabs.0", "@table.grouped.tabs.1"],
						"activeTab": 0,
						"col_keys": [
							{"col_w": 80, "key": "gbm"},
							{"col_w": 100, "key": "plant"},
							{"col_w": 120, "key": ["details", "type"]},
							{"col_w": 90, "key": ["details", "v2024"]},
							{"col_w": 90, "key": ["details", "v2025"]},
							{"col_w": 90, "key": ["details", "v2026"]},
							{"col_w": 90, "key": ["details", "v10"]},
							{"col_w": 90, "key": ["details", "v11"]},
							{"col_w": 90, "key": ["details", "v12"]},
							{"col_w": 90, "key": ["details", "v01"]},
							{"col_w": 100, "key": ["details", "monthly"]},
							{"col_w": 60, "key": ["details", "yearly"]},
						],
						"headers": [
							{"title": "@table.grouped.headers.gbm", "key": "gbm", "col_span": ["details"], "vertical_align": "top", "is_bold": True},
							{"title": "@table.grouped.headers.plant", "key": "plant", "col_span": ["details"], "vertical_align": "top", "is_bold": True},
							{"title": "@table.grouped.headers.type", "key": ["details", "type"]},
							{"title": "2024", "key": ["details", "v2024"]},
							{"title": "2025", "key": ["details", "v2025"]},
							{"title": "2026", "key": ["details", "v2026"]},
							{"title": "2025-10", "key": ["details", "v10"]},
							{"title": "2025-11", "key": ["details", "v11"]},
							{"title": "2025-12", "key": ["details", "v12"]},
							{"title": "2026-01", "key": ["details", "v01"]},
							{"title": "@table.grouped.headers.monthly", "key": ["details", "monthly"]},
							{"title": "@table.grouped.headers.yearly", "key": ["details", "yearly"]},
						],
					},
				},
				# ─── TABLE 3: Data Table (Virtual scroll) ───
				{
					"type": "table_data",
					"title": "@table.layout.data.title",
					"data_key": "table_data",
					"config": {
						"col_keys": [
							{"col_w": 70, "key": None, "align": "center"},
							{"col_w": 100, "key": "no", "align": "right"},
							{"col_w": 120, "key": "vendorCode", "align": "center"},
							{"col_w": 300, "key": "vendorName"},
							{"col_w": 120, "key": "pic"},
							{"col_w": 150, "key": "date", "align": "right"},
							{"col_w": 150, "key": "date1", "align": "right"},
							{"col_w": 150, "key": "date2", "align": "right"},
							{"col_w": 150, "key": "date3", "align": "right"},
						],
						"headers": [
							[
								{"label": "@table.headers.stt", "row_span": 2},
								{"label": "@table.data.headers.group_employee", "col_span": 4},
								{"label": "@table.data.headers.group_status", "col_span": 4},
							],
							[
								{"label": "@table.data.headers.first_name", "row_span": 1},
								{"label": "@table.data.headers.last_name", "row_span": 1},
								{"label": "@table.data.headers.age", "row_span": 1},
								{"label": "@table.data.headers.phone", "row_span": 1},
								{"label": "@table.data.headers.state1", "row_span": 1},
								{"label": "@table.data.headers.state2", "row_span": 1},
								{"label": "@table.data.headers.state3", "row_span": 1},
								{"label": "@table.data.headers.state4"},
							],
						],
					},
				},
			],
			"power_actions": [{"key": 1, "label": "@table.power_actions.1.label", "dialog_id": "dlg_input_system"}],
		},
		"dialogs": {
			"dlg_input_system": {
				"header": {"label": "@dialog.dlg_input_system.header.label", "minimize": True, "maximize": True, "close": True},
				"sections": [
					{
						"type": "column",
						"show": True,
						"label": "@dialog.dlg_input_system.sections.0.label",
						"columns": 4,
						"fields": [
							{"title": {"text": "Vendor Sorting", "require": True}, "options": {"type": "input", "width": 1}},
							{"title": {"text": "Vendor Sorting", "require": True}, "options": {"type": "input", "width": 1}},
							{"title": {"text": "Vendor Sorting", "require": True}, "options": {"type": "input", "width": 1}},
							{"title": {"text": "Vendor Sorting", "require": True}, "options": {"type": "input", "width": 1}},
							{"title": {"text": "Vendor Sorting", "require": True}, "options": {"type": "input", "width": 2}},
							{"title": {"text": "Vendor Sorting", "require": True}, "options": {"type": "input", "width": 2}},
							{"title": {"text": "Vendor Sorting", "require": True}, "options": {"type": "input", "width": 2, "height": 4}},
							{"title": {"text": "Vendor Sorting", "require": True}, "options": {"type": "input", "width": 2}},
							{"title": {"text": "Vendor Sorting", "require": True}, "options": {"type": "input", "width": 2}},
							{"title": {"text": "Vendor Sorting", "require": True}, "options": {"type": "input", "width": 2}},
							{"title": {"text": "Vendor SortingVendor SortingVendor SortingVendor Sorting", "require": True}, "options": {"type": "input", "width": 2}},
						],
					},
					{
						"type": "attachment",
						"show": True,
						"label": "@dialog.dlg_input_system.sections.1.label",
						"validateFiles": {
							"image/*": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
							"video/*": [".mp4", ".mkv", ".avi"],
							"audio/*": [".mp3", ".wav", ".ogg"],
							"text/*": [".txt", ".csv", ".md", ".json", ".xml", ".html", ".css", ".js"],
							"application/*": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".xlsm", ".ppt", ".pptx"],
						},
					},
				],
				"actions": [
					{
						"label": "@dialog.dlg_input_system.actions.0.label",
						"type": "cancel",
						"action": "CLOSE_DIALOG",
						"style": "secondary",
					},
					{
						"label": "@dialog.dlg_input_system.actions.1.label",
						"type": "save",
						"action": "SUBMIT_FORM",
						"style": "primary",
						# ---- Contract gọi API (FE đọc từ response init_data) ----
						"url": "systems/init_data",
						"method": "POST",
						"func": "submit_form",
						"action_id": "dlg_input_system.save",
						# SystemPower.id — BE kiểm tra quyền theo nút (P1.6)
						"power_key": 1,
						# Giá trị mặc định nạp vào form khi mở dialog
						"defaults": {},
						# Field bắt buộc: FE chặn trước, BE validate lại (không tin client)
						"validate": {"required": []},
						# Hành vi sau khi submit thành công
						"on_success": {"refresh": "data", "close_dialog": True, "remove_history": True},
						"confirmation": {
							"title": "@dialog.dlg_input_system.actions.1.confirmation.title",
							"message": "@dialog.dlg_input_system.actions.1.confirmation.message",
							"confirmLabel": "@dialog.dlg_input_system.actions.1.confirmation.confirmLabel",
							"cancelLabel": "@dialog.dlg_input_system.actions.1.confirmation.cancelLabel",
						},
					},
				],
			},
		},
	},
	"data": {
		"search": {
			"org_tree": [
				{
					"id": "1.",
					"label": "SEVT",
					"children": [
						{
							"id": "1.1.",
							"label": "SET QC Team",
							"children": [
								{
									"id": "1.1.1.",
									"label": "IQC G",
									"children": [
										{
											"id": "1.1.1.2.",
											"label": "IQC 2P",
											"children": [
												{"id": "1.1.1.2.1.", "label": "Inno MEC"},
												{"id": "1.1.1.2.2.", "label": "Incoming MEC"},
												{"id": "1.1.1.2.3.", "label": "RMA MEC"},
												{"id": "1.1.1.2.4.", "label": "Trouble MEC"},
												{"id": "1.1.1.2.5.", "label": "New Model MEC"},
											],
										},
									],
								},
							],
						},
					],
				},
			],
			"period_options": [
				{"key": "created_at", "label": "@search.period_options.created_at.label"},
				{"key": "updated_at", "label": "@search.period_options.updated_at.label"},
			],
			"field_options": {
				"multi_status": [
					{"value": "1", "title": "The Shawshank Redemption", "year": 1994},
					{"value": "2", "title": "The Godfather", "year": 1972},
					{"value": "3", "title": "The Godfather: Part II", "year": 1974},
					{"value": "4", "title": "The Dark Knight", "year": 2008},
					{"value": "5", "title": "12 Angry Men", "year": 1957},
					{"value": "6", "title": "Schindler's List", "year": 1993},
					{"value": "7", "title": "Pulp Fiction", "year": 1994},
				],
				"status": [
					{"value": "", "title": "@search.field_options.status.all"},
					{"value": "approval", "title": "@search.field_options.status.approval"},
				],
				"key_shift": [
					{"value": 1, "title": "@search.field_options.key_shift.1"},
					{"value": 2, "title": "@search.field_options.key_shift.2"},
					{"value": 3, "title": "@search.field_options.key_shift.3"},
					{"value": 4, "title": "@search.field_options.key_shift.4"},
				],
				"gender": [
					{"value": 1, "title": "@search.field_options.gender.1"},
					{"value": 2, "title": "@search.field_options.gender.2"},
					{"value": 3, "title": "@search.field_options.gender.3"},
				],
			},
		},
		"table": {
			"kpi_summary": [
				{"label": "@table.kpi_summary.incoming_lot", "value": 12.691, "trend": None},
				{"label": "@table.kpi_summary.inspection_lot", "value": 1.223, "trend": None},
				{"label": "@table.kpi_summary.pass", "value": 12.672, "color": "success.main"},
				{"label": "@table.kpi_summary.fail", "value": 19, "color": "error.main"},
				{"label": "@table.kpi_summary.lot_reject_rate", "value": "1.55%", "trend": "down"},
			],
			# ═══ kpi_table_data → layout type: table_kpi (row → subGroups[] → details[]) ═══
			"kpi_table_data": [
				{
					"stt": 1, "col1": "Incoming Lot - Mô hình QC", "col2": "Tổng cộng", "col4": "Tổng hợp",
					"subGroups": [
						{"col3": "Pass Lot", "col5": "Đạt yêu cầu", "details": [{"col6": "30 Lot", "col7": "98.45%"}, {"col6": "32 Lot", "col7": "99.12%"}]},
						{"col3": "Fail Lot", "col5": "Không đạt", "details": [{"col6": "2 Lot", "col7": "1.55%"}, {"col6": "1 Lot", "col7": "0.88%"}]},
					],
				},
				{
					"stt": 2, "col1": "Incoming Lot - Mô hình Assembly", "col2": "Tổng cộng", "col4": "Tổng hợp",
					"subGroups": [
						{"col3": "Pass Lot", "col5": "Đạt yêu cầu", "details": [{"col6": "50 Lot", "col7": "97.06%"}, {"col6": "48 Lot", "col7": "96.00%"}]},
						{"col3": "Fail Lot", "col5": "Không đạt", "details": [{"col6": "3 Lot", "col7": "2.94%"}, {"col6": "4 Lot", "col7": "4.00%"}]},
					],
				},
				{
					"stt": 3, "col1": "Incoming Lot - Mô hình SMT", "col2": "Tổng cộng", "col4": "Tổng hợp",
					"subGroups": [
						{"col3": "Pass Lot", "col5": "Đạt yêu cầu", "details": [{"col6": "80 Lot", "col7": "98.77%"}, {"col6": "82 Lot", "col7": "99.39%"}]},
						{"col3": "Fail Lot", "col5": "Không đạt", "details": [{"col6": "1 Lot", "col7": "1.23%"}, {"col6": "0 Lot", "col7": "0.61%"}]},
					],
				},
				{
					"stt": 4, "col1": "Incoming Lot - Mô hình Packing", "col2": "Tổng cộng", "col4": "Tổng hợp",
					"subGroups": [
						{"col3": "Pass Lot", "col5": "Đạt yêu cầu", "details": [{"col6": "120 Lot", "col7": "99.17%"}, {"col6": "115 Lot", "col7": "98.30%"}]},
						{"col3": "Fail Lot", "col5": "Không đạt", "details": [{"col6": "1 Lot", "col7": "0.83%"}, {"col6": "2 Lot", "col7": "1.70%"}]},
					],
				},
				{
					"stt": 5, "col1": "Incoming Lot - Mô hình Testing", "col2": "Tổng cộng", "col4": "Tổng hợp",
					"subGroups": [
						{"col3": "Pass Lot", "col5": "Đạt yêu cầu", "details": [{"col6": "200 Lot", "col7": "99.50%"}, {"col6": "198 Lot", "col7": "99.49%"}]},
						{"col3": "Fail Lot", "col5": "Không đạt", "details": [{"col6": "1 Lot", "col7": "0.50%"}, {"col6": "1 Lot", "col7": "0.51%"}]},
					],
				},
			],
			# ═══ table_grouped → layout type: table_grouped (gbm, plant, details[]) ═══
			"table_grouped": [
				{
					"gbm": "MX", "plant": "SEVT",
					"details": [
						{"type": "Total", "v2024": 1.558, "v2025": 1.128, "v2026": 976, "v10": 828, "v11": 541, "v12": 752, "v01": 976, "monthly": 30, "yearly": 13, "isBold": True},
						{"type": "Insp. Q'ty", "v2024": 7827.522, "v2025": 7258.154, "v2026": 348.43, "v10": 437.274, "v11": 423.446, "v12": 437.507, "v01": 348.43, "monthly": None, "yearly": None},
						{"type": "Defect Q'ty", "v2024": 12.199, "v2025": 8.19, "v2026": 340, "v10": 362, "v11": 229, "v12": 329, "v01": 340, "monthly": None, "yearly": None},
						{"type": "Reject Rate", "v2024": "0.16%", "v2025": "0.11%", "v2026": "0.10%", "v10": "0.08%", "v11": "0.05%", "v12": "0.08%", "v01": "0.10%", "monthly": None, "yearly": None},
					],
				},
				{
					"gbm": "MX", "plant": "SZVT",
					"details": [
						{"type": "Total", "v2024": 2.341, "v2025": 1.876, "v2026": 1.203, "v10": 987, "v11": 856, "v12": 1.102, "v01": 1.203, "monthly": 25, "yearly": 18, "isBold": True},
						{"type": "Insp. Q'ty", "v2024": 12543.891, "v2025": 11234.567, "v2026": 987.654, "v10": 876.543, "v11": 812.345, "v12": 865.432, "v01": 987.654, "monthly": None, "yearly": None},
						{"type": "Defect Q'ty", "v2024": 29.265, "v2025": 21.065, "v2026": 11.875, "v10": 8.642, "v11": 6.952, "v12": 9.534, "v01": 11.875, "monthly": None, "yearly": None},
						{"type": "Reject Rate", "v2024": "0.23%", "v2025": "0.19%", "v2026": "0.12%", "v10": "0.10%", "v11": "0.09%", "v12": "0.11%", "v01": "0.12%", "monthly": None, "yearly": None},
					],
				},
				{
					"gbm": "MX", "plant": "HCVT",
					"details": [
						{"type": "Total", "v2024": 3.125, "v2025": 2.456, "v2026": 1.89, "v10": 1.543, "v11": 1.321, "v12": 1.678, "v01": 1.89, "monthly": 42, "yearly": 29, "isBold": True},
						{"type": "Insp. Q'ty", "v2024": 18765.432, "v2025": 16543.21, "v2026": 1543.21, "v10": 1234.567, "v11": 1198.765, "v12": 1287.654, "v01": 1543.21, "monthly": None, "yearly": None},
						{"type": "Defect Q'ty", "v2024": 58.665, "v2025": 40.653, "v2026": 29.19, "v10": 19.095, "v11": 15.831, "v12": 21.624, "v01": 29.19, "monthly": None, "yearly": None},
						{"type": "Reject Rate", "v2024": "0.31%", "v2025": "0.25%", "v2026": "0.19%", "v10": "0.15%", "v11": "0.13%", "v12": "0.17%", "v01": "0.19%", "monthly": None, "yearly": None},
					],
				},
				{
					"gbm": "JP", "plant": "SEVT",
					"details": [
						{"type": "Total", "v2024": 1.876, "v2025": 1.543, "v2026": 1.102, "v10": 934, "v11": 812, "v12": 1.023, "v01": 1.102, "monthly": 18, "yearly": 12, "isBold": True},
						{"type": "Insp. Q'ty", "v2024": 9876.543, "v2025": 8765.432, "v2026": 876.543, "v10": 765.432, "v11": 723.456, "v12": 798.765, "v01": 876.543, "monthly": None, "yearly": None},
						{"type": "Defect Q'ty", "v2024": 18.565, "v2025": 13.499, "v2026": 9.642, "v10": 7.14, "v11": 5.846, "v12": 8.167, "v01": 9.642, "monthly": None, "yearly": None},
						{"type": "Reject Rate", "v2024": "0.19%", "v2025": "0.15%", "v2026": "0.11%", "v10": "0.09%", "v11": "0.08%", "v12": "0.10%", "v01": "0.11%", "monthly": None, "yearly": None},
					],
				},
				{
					"gbm": "JP", "plant": "SZVT",
					"details": [
						{"type": "Total", "v2024": 2.654, "v2025": 2.109, "v2026": 1.654, "v10": 1.321, "v11": 1.198, "v12": 1.456, "v01": 1.654, "monthly": 35, "yearly": 22, "isBold": True},
						{"type": "Insp. Q'ty", "v2024": 14321.098, "v2025": 12987.654, "v2026": 1321.098, "v10": 1098.765, "v11": 1054.321, "v12": 1176.543, "v01": 1321.098, "monthly": None, "yearly": None},
						{"type": "Defect Q'ty", "v2024": 37.932, "v2025": 27.409, "v2026": 21.865, "v10": 14.514, "v11": 12.617, "v12": 17.137, "v01": 21.865, "monthly": None, "yearly": None},
						{"type": "Reject Rate", "v2024": "0.26%", "v2025": "0.21%", "v2026": "0.17%", "v10": "0.13%", "v11": "0.12%", "v12": "0.15%", "v01": "0.17%", "monthly": None, "yearly": None},
					],
				},
			],
			# ═══ table_data → layout type: table_data (Danh sách Master Vendor) ═══
			"table_data": [
				{"id": 1, "no": 1, "vendorCode": "DK18", "vendorName": "DAE RIM PRECISION CO., LTD.", "pic": "SYSTEM", "date": "16/12/2018", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 2, "no": 2, "vendorCode": "DK19", "vendorName": "SHIN KWANG SEALING PRINTING CO.", "pic": "SYSTEM", "date": "16/12/2018", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 3, "no": 3, "vendorCode": "DK20", "vendorName": "HANA MICRON VIETNAM CO., LTD.", "pic": "NGUYEN VAN A", "date": "22/03/2019", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 4, "no": 4, "vendorCode": "DK21", "vendorName": "SAMSUNG ELECTRONICS VIETNAM CO., LTD.", "pic": "TRAN VAN B", "date": "15/06/2019", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 5, "no": 5, "vendorCode": "DK22", "vendorName": "FOXCONN TECHNOLOGY VIETNAM CO., LTD.", "pic": "SYSTEM", "date": "01/09/2019", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 6, "no": 6, "vendorCode": "DK23", "vendorName": "LG DISPLAY VIETNAM CO., LTD.", "pic": "LE VAN C", "date": "18/11/2019", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 7, "no": 7, "vendorCode": "DK24", "vendorName": "PANASONIC SYSTEM NETWORKS VIETNAM CO.", "pic": "SYSTEM", "date": "03/02/2020", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 8, "no": 8, "vendorCode": "DK25", "vendorName": "INNOLUX DISPLAY TECHNOLOGY VIETNAM", "pic": "PHAM VAN D", "date": "27/04/2020", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 9, "no": 9, "vendorCode": "DK26", "vendorName": "BOE TECHNOLOGY GROUP VIETNAM CO.", "pic": "SYSTEM", "date": "10/07/2020", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 10, "no": 10, "vendorCode": "DK27", "vendorName": "TIANMA MICROELECTRONICS VIETNAM CO.", "pic": "HOANG VAN E", "date": "05/09/2020", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 11, "no": 11, "vendorCode": "DK28", "vendorName": "AU OPTRONICS VIETNAM CO., LTD.", "pic": "SYSTEM", "date": "20/11/2020", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 12, "no": 12, "vendorCode": "DK29", "vendorName": "TRULY OPTO-ELECTRONICS VIETNAM CO.", "pic": "VO VAN F", "date": "14/01/2021", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 13, "no": 13, "vendorCode": "DK30", "vendorName": "NICHIA CHEMICAL VIETNAM CO., LTD.", "pic": "SYSTEM", "date": "08/03/2021", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 14, "no": 14, "vendorCode": "DK31", "vendorName": "TOSHIBA MEMORY VIETNAM CO., LTD.", "pic": "DANG VAN G", "date": "29/05/2021", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 15, "no": 15, "vendorCode": "DK32", "vendorName": "KYOCERA VIETNAM CO., LTD.", "pic": "SYSTEM", "date": "17/08/2021", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 16, "no": 16, "vendorCode": "DK33", "vendorName": "ALPS ALPINE VIETNAM CO., LTD.", "pic": "BUI VAN H", "date": "22/10/2021", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 17, "no": 17, "vendorCode": "DK34", "vendorName": "TDK VIETNAM MANUFACTURING CO., LTD.", "pic": "SYSTEM", "date": "09/12/2021", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 18, "no": 18, "vendorCode": "DK35", "vendorName": "MURATA MANUFACTURING VIETNAM CO., LTD.", "pic": "NGUYEN VAN I", "date": "11/02/2022", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 19, "no": 19, "vendorCode": "DK36", "vendorName": "ROHM SEMICONDUCTOR VIETNAM CO., LTD.", "pic": "SYSTEM", "date": "25/04/2022", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 20, "no": 20, "vendorCode": "DK37", "vendorName": "OMRON ELECTRONIC COMPONENTS VIETNAM", "pic": "TRINH VAN J", "date": "30/06/2022", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 21, "no": 21, "vendorCode": "DK38", "vendorName": "YAGEO CORPORATION VIETNAM CO., LTD.", "pic": "SYSTEM", "date": "13/09/2022", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 22, "no": 22, "vendorCode": "DK39", "vendorName": "WALSIN TECHNOLOGY VIETNAM CO., LTD.", "pic": "MAI VAN K", "date": "07/11/2022", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 23, "no": 23, "vendorCode": "DK40", "vendorName": "SAMSUNG SDI VIETNAM CO., LTD.", "pic": "SYSTEM", "date": "19/01/2023", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 24, "no": 24, "vendorCode": "DK41", "vendorName": "CATL VIETNAM ENERGY TECHNOLOGY CO.", "pic": "LE VAN L", "date": "15/03/2023", "date1": "-", "date2": "-", "date3": "-"},
				{"id": 25, "no": 25, "vendorCode": "DK42", "vendorName": "BYD VIETNAM ELECTRONICS CO., LTD.", "pic": "SYSTEM", "date": "28/05/2023", "date1": "-", "date2": "-", "date3": "-"},
			],
		},
	},
	# ═══ INITIAL_STATE: Trạng thái runtime mặc định (defaults vs current) ═══
	"initial_state": {
		"defaults": {
			"active_view": "views",
			"search_ui": {"org": True, "period": True, "details": True},
			"query": {
				"org": ["1.1.1.2.1.", "1.1.1.2.2."],
				"period": {"select": "created_at", "from": "2025-12-01", "to": "2025-12-14", "range": 30},
				"limit": 50,
				"offset": 0,
				"details": {},
			},
			"org_slide": ["1.", "1.1.", "1.1.1.", "1.1.1.2."],
		},
		"current": {
			"active_view": "views",
			"search_ui": {"org": True, "period": True, "details": True},
			"query": {
				"org": ["1.1.1.2.1.", "1.1.1.2.2."],
				"period": {"select": "created_at", "from": "2025-12-01", "to": "2025-12-14"},
				"limit": 50,
				"offset": 0,
				"details": {},
			},
			"org_slide": ["1.", "1.1.", "1.1.1.", "1.1.1.2."],
			"confirmation": None,
			# None — dialog chỉ mở khi bấm nút chức năng (power_actions),
			# không tự mở khi hydrate (cần FE có reducer openDialog — P2).
			"active_dialog_id": None,
			"dialog_list": {},
		},
	},
}
