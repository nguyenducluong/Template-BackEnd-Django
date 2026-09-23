"""
Translation riêng của Systems Details — KHÔNG dùng gettext locale của project/system.

Cơ chế:
- Payload đánh dấu chuỗi UI bằng marker ``"@key"`` (chuỗi bắt đầu dấu @).
- Mỗi header có ``systems_details/{header_id}/translations.py``:
    TRANSLATIONS = {"key": {"vi": "...", "en": "...", "kr": "..."}}
- ``translate_details`` deep-walk payload (dict/list) và thay marker theo lang
  (request.LANGUAGE_CODE từ header Accept-Language frontend đã gửi).
- Fallback: lang không có → en → vi → trả lại key (bỏ dấu @) — không crash khi thiếu.
- Chuỗi không đánh dấu (org_tree, vendor, dữ liệu bảng) là DATA — giữ nguyên.
"""

import copy
import importlib

LANGUAGES = ("vi", "en", "kr")
DEFAULT_LANG = "vi"
MARKER_PREFIX = "@"

_cache = {}


def get_header_translations(header_id):
    """Đọc TRANSLATIONS của systems_details/{header_id}/translations.py (cache theo header)."""
    if header_id not in _cache:
        try:
            module = importlib.import_module(f"apps.systems.systems_details.{header_id}.translations")
            _cache[header_id] = getattr(module, "TRANSLATIONS", {})
        except ModuleNotFoundError:
            _cache[header_id] = {}
    return _cache[header_id]


def _resolve(marker_key, lang, translations):
    """Tra 1 key marker → bản dịch; fallback en → vi → key (bỏ dấu @)."""
    key = marker_key.lstrip(MARKER_PREFIX)
    entry = translations.get(key)
    if not entry:
        return key
    if isinstance(entry, str):
        return entry
    return entry.get(lang) or entry.get("en") or entry.get(DEFAULT_LANG) or key


def translate_details(obj, lang, translations):
    """Đệ quy thay marker trong dict/list/tuple; các kiểu khác giữ nguyên."""
    if isinstance(obj, dict):
        return {key: translate_details(value, lang, translations) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        translated = [translate_details(item, lang, translations) for item in obj]
        return type(obj)(translated) if isinstance(obj, tuple) else translated
    if isinstance(obj, str) and obj.startswith(MARKER_PREFIX):
        return _resolve(obj, lang, translations)
    return obj


def translate_payload(payload, lang, header_id):
    """Deepcopy payload rồi thay marker theo lang. Header chưa có translations → trả nguyên."""
    translations = get_header_translations(header_id)
    if not translations:
        return payload
    normalized = lang if lang in LANGUAGES else DEFAULT_LANG
    return translate_details(copy.deepcopy(payload), normalized, translations)
