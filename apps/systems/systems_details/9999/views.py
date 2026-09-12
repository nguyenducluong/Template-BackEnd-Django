"""
Header 9999 — Demo folder (không map với SystemHeader thật).

Dùng để test dispatcher: gọi header_id=9999 sẽ trả base mock data.
"""

from apps.systems.systems_details.base_system import (  # noqa: F401
	action,
	chart,
	dashboard,
	definition,
	download,
	search,
)
