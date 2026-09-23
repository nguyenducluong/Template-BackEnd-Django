"""
Nhãn UI trang Auth (vi/en/kr) — port từ Laravel ``app/Views/DefineAppView.php``.

Endpoint consumer: GET /api/v1/system/default/options_authentication (apps/systems/default/views.py)
Chọn ngôn ngữ theo ``Accept-Language`` (LanguageMiddleware đã chuẩn hóa về vi/en/kr).
"""

# ---- Tiêu đề trang ----
PAGE_TITLE = {
	"sign_in": {
		"en": "Sign In",
		"vi": "Đăng nhập",
		"kr": "로그인",
	},
	"change_password": {
		"en": "Change Password",
		"vi": "Đổi mật khẩu",
		"kr": "비밀번호 변경",
	},
	"unlock_user": {
		"en": "Unlock User",
		"vi": "Mở khóa tài khoản",
		"kr": "사용자 잠금 해제",
	},
	"user_info": {
		"en": "User Information",
		"vi": "Thông tin người dùng",
		"kr": "사용자 정보",
	},
}

# ---- Đường kẻ (divider) ----
PAGE_DIVIDER = {
	"other_sign_in": {
		"en": "Or sign in with",
		"vi": "Hoặc đăng nhập bằng",
		"kr": "다른 계정으로 로그인",
	},
	"contact": {
		"en": "Contact Information",
		"vi": "Thông tin liên hệ",
		"kr": "연락처 정보",
	},
}

# ---- Button ----
PAGE_BUTTON = {
	"sign_in": {
		"en": "Sign In",
		"vi": "Đăng nhập",
		"kr": "로그인",
	},
	"change_password": {
		"en": "Change Password",
		"vi": "Đổi mật khẩu",
		"kr": "비밀번호 변경",
	},
	"otp_required": {
		"en": "OTP Required",
		"vi": "Yêu cầu OTP",
		"kr": "OTP가 필요합니다",
	},
	"otp_valid": {
		"en": "Unlock",
		"vi": "Mở khóa",
		"kr": "잠금 해제",
	},
	"ckb_save_user": {
		"en": "Remember account",
		"vi": "Lưu tài khoản",
		"kr": "계정 저장",
	},
	"ad_sso_corp": {
		"en": "AD SSO (Samsung Sign On)",
		"vi": "AD SSO (Đăng nhập bằng CORP)",
		"kr": "AD SSO (삼성 계정 로그인)",
	},
}

# ---- Các ô input ----
PAGE_INPUT = {
	"knox_id": {
		"title": {
			"en": "Knox ID or Gen ID",
			"vi": "Mã nhân viên hoặc KnoxID",
			"kr": "녹스 아이디 또는 겐 아이디",
		},
		"placeholder": {
			"en": "Enter your Knox ID or Gen ID",
			"vi": "Nhập mã nhân viên hoặc KnoxID",
			"kr": "녹스 아이디 또는 겐 아이디를 입력하세요",
		},
		"msg_required": {
			"en": "Knox ID or Gen ID is required",
			"vi": "Mã nhân viên hoặc KnoxID là bắt buộc",
			"kr": "녹스 아이디 또는 겐 아이디는 필수입니다",
		},
		"msg_pattern": {
			"vi": "KnoxID ít nhất 5 ký tự hoặc mã GenID phải là 8 chữ số",
			"en": "KnoxID must be at least 5 characters or GenID must be 8 digits",
			"kr": "녹스 아이디는 최소 5자 이상이어야 하며, 겐 아이디는 8자리 숫자여야 합니다",
		},
	},
	"password": {
		"title": {
			"en": "Password",
			"vi": "Mật khẩu",
			"kr": "비밀번호",
		},
		"placeholder": {
			"en": "Enter your password",
			"vi": "Nhập mật khẩu của bạn",
			"kr": "비밀번호를 입력하세요",
		},
		"msg_required": {
			"en": "Password is required",
			"vi": "Mật khẩu là bắt buộc",
			"kr": "비밀번호는 필수입니다",
		},
		"msg_pattern": {
			"en": "Password must contain at least one letter or special character and one number and be at least 8 characters long",
			"vi": "Mật khẩu phải chứa ít nhất một chữ cái hoặc ký tự đặc biệt và một số, tối thiểu 8 ký tự",
			"kr": "비밀번호는 최소 8자 이상이어야 하며, 최소 하나의 문자 또는 특수 문자와 하나의 숫자를 포함해야 합니다",
		},
	},
	"old_password": {
		"title": {
			"en": "Current Password",
			"vi": "Mật khẩu hiện tại",
			"kr": "현재 비밀번호",
		},
		"placeholder": {
			"en": "Enter current password",
			"vi": "Nhập mật khẩu hiện tại",
			"kr": "현재 비밀번호를 입력하세요",
		},
		"msg_required": {
			"en": "Current password is required",
			"vi": "Mật khẩu hiện tại là bắt buộc",
			"kr": "현재 비밀번호는 필수입니다",
		},
	},
	"new_password": {
		"title": {
			"en": "New Password",
			"vi": "Mật khẩu mới",
			"kr": "새 비밀번호",
		},
		"placeholder": {
			"en": "Enter new password",
			"vi": "Nhập mật khẩu mới",
			"kr": "새 비밀번호를 입력하세요",
		},
		"msg_required": {
			"en": "New password is required",
			"vi": "Mật khẩu mới là bắt buộc",
			"kr": "새 비밀번호는 필수입니다",
		},
		"msg_validate": {
			"en": "New password cannot be the same as the old password",
			"vi": "Mật khẩu mới không được giống mật khẩu cũ",
			"kr": "새 비밀번호는 기존 비밀번호와 같을 수 없습니다",
		},
		"msg_pattern": {
			"en": "Password must contain at least one letter or special character and one number and be at least 8 characters long",
			"vi": "Mật khẩu phải chứa ít nhất một chữ cái hoặc ký tự đặc biệt và một số, tối thiểu 8 ký tự",
			"kr": "비밀번호는 최소 8자 이상이어야 하며, 최소 하나의 문자 또는 특수 문자와 하나의 숫자를 포함해야 합니다",
		},
	},
	"re_new_password": {
		"title": {
			"en": "Confirm New Password",
			"vi": "Xác nhận mật khẩu mới",
			"kr": "새 비밀번호 확인",
		},
		"placeholder": {
			"en": "Re-enter new password",
			"vi": "Nhập lại mật khẩu mới",
			"kr": "새 비밀번호를 다시 입력하세요",
		},
		"msg_required": {
			"en": "Please confirm your new password",
			"vi": "Vui lòng xác nhận mật khẩu mới",
			"kr": "Vui lòng xác nhận mật khẩu mới",
		},
		"msg_validate": {
			"en": "Passwords do not match",
			"vi": "Mật khẩu xác nhận không khớp",
			"kr": "비밀번호가 일치하지 않습니다",
		},
	},
	"otp": {
		"title": {
			"en": "OTP Code",
			"vi": "Mã OTP",
			"kr": "OTP 번호",
		},
		"msg_required": {
			"en": "This field is required",
			"vi": "Trường bắt buộc cần nhập",
			"kr": "필수 입력 항목입니다",
		},
		"msg_pattern": {
			"en": "OTP must be a 6-digit number",
			"vi": "Mã OTP là số và có độ dài 6 số",
			"kr": "OTP는 6자리 숫자여야 합니다",
		},
	},
	"org_full_name": {
		"title": {
			"en": "Working Group",
			"vi": "Nhóm làm việc",
			"kr": "작업 그룹",
		},
	},
	"full_name": {
		"title": {
			"en": "Full Name",
			"vi": "Họ và tên",
			"kr": "성명",
		},
	},
	"ipv4": {
		"title": {
			"en": "IP Address",
			"vi": "Địa chỉ máy tính",
			"kr": "IP 주소",
		},
	},
	"status_label": {
		"title": {
			"en": "Account Status",
			"vi": "Trạng thái tài khoản",
			"kr": "계정 상태",
		},
	},
}


def build_init_options(language: str) -> dict:
	"""Dựng object `init` (title/button/input/divider) theo ngôn ngữ.

	Tương ứng Laravel DefineAppView::opt_label().
	"""
	lang = language if language in ("vi", "en", "kr") else "vi"
	return {
		"title": {key: value[lang] for key, value in PAGE_TITLE.items()},
		"button": {key: value[lang] for key, value in PAGE_BUTTON.items()},
		"input": {
			key: {sub_key: sub_value[lang] for sub_key, sub_value in value.items()}
			for key, value in PAGE_INPUT.items()
		},
		"divider": {key: value[lang] for key, value in PAGE_DIVIDER.items()},
	}