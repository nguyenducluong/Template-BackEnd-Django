"""
Seed toàn bộ dữ liệu mẫu theo các file SQL trong `database/mysql/iqcg/`:

- `_0002 organizations.sql`    -> Organization (Company > Team > Group > Part > Location)
- `_0006_shift.sql`            -> Shift
- `_0020-21_vendor,material`   -> Vendor / Material (data example)
- `_0030-33_header.sql`        -> GroupHeader / PagesHeader / SystemHeader / SystemPower
- `_0010_user.sql`             -> User mẫu (Nguyễn Đức Lương)
- `_0035~40 public system.sql` -> HeaderRegistration cho MOI SystemHeader
                                  + hieu ung trigger vao HeaderOrganization / UserHeaderRegistration,
                                  va SystemPermission example
"""

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.info.models import (
    GroupHeader,
    HeaderOrganization,
    HeaderOrganizationUserRegistration,
    HeaderRegistration,
    Material,
    Organization,
    PagesHeader,
    Shift,
    SystemHeader,
    SystemPower,
    SystemPermission,
    UserHeaderRegistration,
    UserSystemPermissionRegistration,
    Vendor,
)


class Command(BaseCommand):
    help = "Seed all example data from iqcg SQL files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Delete existing data before seeding (children first)",
        )

    # ------------------------------------------------------------------
    # - `_0002 organizations.sql`    -> Organization (Company > Team > Group > Part > Location)
    # ------------------------------------------------------------------
    # id, parent_id, level, name, sort, is_use
    # level dung Organization.LevelChoices:
    #   0 Company - 1 Team - 2 Group - 3 Part - 4 Location
    ORGS = [
        (1, None, 0, "SEVT", 1, True),
        (2, 1, 1, "SET QC Team", 1, True),
        (3, 2, 2, "IQC G", 1, True),
        (4, 3, 3, "IQC 1P", 1, True),
        (5, 3, 3, "IQC 2P", 2, True),
        (6, 3, 3, "IQC 3P", 3, True),
        (11, 4, 4, "System", 1, True),
        (12, 4, 4, "CKD / SKD", 2, True),
        (13, 4, 4, "Semi", 3, True),
        (14, 4, 4, "Reliability (DTC)", 4, True),
        (15, 4, 4, "Inno MEC", 5, True),
        (21, 5, 4, "Inno MEC", 1, True),
        (22, 5, 4, "Incoming MEC", 2, True),
        (23, 5, 4, "Trouble MEC", 3, True),
        (24, 5, 4, "RMA MEC", 4, True),
        (25, 5, 4, "New Model", 5, True),
        (31, 6, 4, "Inno ELE", 1, True),
        (32, 6, 4, "Incoming ELE", 2, True),
        (33, 6, 4, "Trouble ELE", 3, True),
        (34, 6, 4, "RMA ELE", 4, True),
    ]

    def _seed_organizations(self):
        for org_id, pid, level, name, sort, is_use in self.ORGS:
            Organization.objects.update_or_create(
                id=org_id,
                defaults={
                    "parent_id": pid,
                    "level": level,
                    "name": name,
                    "sort": sort,
                    "is_use": is_use,
                },
            )
        # Populate cached hierarchy fields after all orgs are created
        for org in Organization.objects.all():
            org.save()  # triggers cache computation

    # ------------------------------------------------------------------
    # _0006_shift.sql
    # ------------------------------------------------------------------
    SHIFTS = [
        (1, "Hành chính", "Staff A1", "Staff A1"),
        (2, "Shift 1", "Shift 1A1", "Shift 1A1"),
        (3, "Shift 2", "Shift 2A1", "Shift 2A1"),
    ]

    def _seed_shifts(self):
        for sid, vi, en, kr in self.SHIFTS:
            Shift.objects.update_or_create(
                id=sid, defaults={"shift_vi": vi, "shift_en": en, "shift_kr": kr}
            )

    # ------------------------------------------------------------------
    # _0020-21 — SQL gốc không có INSERT, dùng data example
    # ------------------------------------------------------------------
    VENDORS = [
        ("SAMSUNG", "Samsung Electronics", True, False),
        ("LG-INV", "LG Innotek", True, False),
        ("SEMCO", "Samsung Electro-Mechanics", True, False),
        ("MURATA", "Murata Manufacturing", True, False),
        ("TDK-ELE", "TDK Electronics", False, True),
    ]

    def _seed_vendors(self):
        for code, name, is_use, is_replace in self.VENDORS:
            Vendor.objects.update_or_create(
                vendor_code=code,
                defaults={
                    "vendor_name": name,
                    "is_use": is_use,
                    "is_replace": is_replace,
                },
            )

    MATERIALS = [
        ("A30FBRG003A", "SM-A305", "SM-A305F", "Main PCB", "Main Printed Circuit Board", None, 1, False),
        ("A30FBRG004A", "SM-A305", "SM-A305F", "Battery", "Battery Pack 4000mAh", "Black", 1, False),
        ("A50FBRG011S", "SM-A505", "SM-A505S", "Display", "Display Module PLS", "White", 1, False),
        ("A50FCAM021A", "SM-A505", "SM-A505F", "Camera F", "Front Camera Module 25MP", None, 2, True),
        ("A20FCHG005A", "SM-A205", "SM-A205F", "Charger", "Charger Adapter 15W", None, 3, False),
    ]

    def _seed_materials(self):
        for code, model, model_full, pname, pname_full, color, group, is_manual in self.MATERIALS:
            Material.objects.update_or_create(
                material_code=code,
                defaults={
                    "model": model,
                    "model_full": model_full,
                    "part_name": pname,
                    "part_name_full": pname_full,
                    "color": color,
                    "group": group,
                    "is_manual": bool(is_manual),
                },
            )

    # ------------------------------------------------------------------
    # _0030-33_header.sql
    # ------------------------------------------------------------------
    GROUP_HEADERS = [
        (1, 1, True, "Hệ thống khác", "Other system", "다른 시스템"),
        (2, 2, True, "Mẫu", "Sample", "샘플"),
        (3, 3, True, "Tiêu chuẩn", "Standard", "표준"),
        (4, 4, True, "Kết quả", "Result", "결과"),
        (5, 5, True, "Báo cáo", "Report", "보고서"),
        (6, 6, True, "Thiết bị", "Equipment", "장비"),
        (7, 7, True, "Hướng dẫn", "Manual", "매뉴얼"),
        (8, 8, True, "Dữ liệu", "Master data", "마스터 데이터"),
        (9, 9, True, "Hệ thống", "System", "시스템"),
        (10, 10, True, "Phát triển", "Developer", "개발자"),
    ]

    def _seed_group_headers(self):
        for gid, sort, is_use, vi, en, kr in self.GROUP_HEADERS:
            GroupHeader.objects.update_or_create(
                id=gid,
                defaults={
                    "sort": sort, "is_use": is_use,
                    "group_vi": vi, "group_en": en, "group_kr": kr,
                },
            )

    PAGES_HEADERS = [
        (1, 1, 1, 1, "Hệ thống SQCI 3.0", "System SQCI 3.0", "시스템 SQCI 3.0"),
        (2, 1, 2, 1, "Hệ thống SPLM", "System SPLM", "시스템 SPLM"),
        (3, 1, 3, 1, "Hệ thống NERP", "System NERP", "시스템 NERP"),
        (4, 2, 1, 1, "Yêu cầu mẫu", "Request sample", "샘플 요청"),
        (5, 2, 2, 1, "Mẫu chuẩn", "Master sample", "마스터 샘플"),
        (6, 2, 3, 1, "Mẫu limit", "Limit sample", "샘플 한정"),
        (7, 2, 3, 1, "Mẫu first lot", "First lot sample", "첫 번째 샘플"),
    ]

    def _seed_pages_headers(self):
        for pid, gh_id, is_use, sort, vi, en, kr in self.PAGES_HEADERS:
            PagesHeader.objects.update_or_create(
                id=pid,
                defaults={
                    "group_header_id": gh_id,
                    "is_use": bool(is_use), "sort": sort,
                    "page_vi": vi, "page_en": en, "page_kr": kr,
                },
            )

    SYSTEM_HEADERS = [
        (1, 1, 1, 1, 0,
         "Waiting for IQC", "Waiting for IQC", "입고검사대상 및 결과입력",
         "Waiting for IQC", "Waiting for IQC", "입고검사대상 및 결과입력"),
        (2, 1, 2, 1, 0,
         "IQC Inspection Result", "IQC Inspection Result", "검사실적 및 처리현황",
         "IQC Inspection Result", "IQC Inspection Result", "검사실적 및 처리현황"),
        (3, 1, 3, 1, 0,
         "Spec Input", "Spec Input", "Spec 입력 목록",
         "Spec Input", "Spec Input", "Spec 입력 목록"),
        (4, 1, 4, 1, 0,
         "Inspection Standard Library", "Inspection Standard Library", "검사기준서 관리",
         "Inspection Standard Library", "Inspection Standard Library", "검사기준서 관리"),
        (5, 1, 5, 1, 0,
         "Part DMR", "Part DMR", "Part DMR 설정",
         "Part DMR", "Part DMR", "Part DMR 설정"),
    ]

    def _seed_system_headers(self):
        for (sid, ph_id, sort, is_use, is_mobile, view_vi, view_en, view_kr,
             header_vi, header_en, header_kr) in self.SYSTEM_HEADERS:
            SystemHeader.objects.update_or_create(
                id=sid,
                defaults={
                    "page_header_id": ph_id,
                    "sort": sort, "is_use": is_use, "is_mobile": bool(is_mobile),
                    "view_vi": view_vi, "view_en": view_en, "view_kr": view_kr,
                    "header_vi": header_vi, "header_en": header_en, "header_kr": header_kr,
                },
            )

    SYSTEM_POWERS = [
        (1, 1, 1, 1, "Lưu chú thích memo SQCI", "Save memo SQCI", "메모 저장 SQCI"),
    ]

    def _seed_system_powers(self):
        for pid, sh_id, is_use, sort, vi, en, kr in self.SYSTEM_POWERS:
            SystemPower.objects.update_or_create(
                id=pid,
                defaults={
                    "system_header_id": sh_id,
                    "is_use": is_use, "sort": sort,
                    "power_vi": vi, "power_en": en, "power_kr": kr,
                },
            )

    # ------------------------------------------------------------------
    # _0010_user.sql — password gốc 'Luongka97*' được hash lại bằng
    # PBKDF2 của Django thay vì bcrypt string trong SQL
    # ------------------------------------------------------------------
    def _seed_user(self):
        org = Organization.objects.get(id=22)
        shift = Shift.objects.get(id=3)
        user, created = User.objects.get_or_create(
            gen_id="18764398",
            defaults={
                "knox_id": "luong97.duc",
                "full_name": "Nguyễn Đức Lương",
                "org": org,
                "shift": shift,
                "status": User.StatusChoices.APPROVED,
                "ip_remember": "127.0.0.1",
            },
        )
        if created:
            user.set_password("Luongka97*")
            user.save(update_fields=["password"])
        return user

    # ------------------------------------------------------------------
    # _0035~40 public system.sql - HeaderRegistration cho moi SystemHeader
    # ------------------------------------------------------------------
    def _seed_registrations(self, user):
        # Bo phan mac dinh: org 22 = 'Incoming MEC' (nhom IQC 2P)
        org_id = 22
        # Lay TAT CA SystemHeader da seed (khong hardcode id) de moi header deu co
        # mot dang ky HeaderRegistration hop le - tranh tinh trang header khong
        # duoc gan quyen va khong mo duoc man hinh.
        headers = list(SystemHeader.objects.all().order_by("sort", "id"))
        if not headers:
            self.stdout.write(self.style.WARNING("  No SystemHeader found - skip registrations"))
            return

        registrations = []
        for header in headers:
            # _0035: dang ky header cho bo phan
            hr, _ = HeaderRegistration.objects.update_or_create(
                org_id=org_id,
                header_id=header.id,
                defaults={
                    "registered_by": user,
                    "approved_by": user,
                    "type": HeaderRegistration.TypeChoices.NO_REGISTRATION,
                    "status": HeaderRegistration.StatusChoices.APPROVED,
                },
            )
            registrations.append(hr)

            # Trigger trg_after_insert_0035 -> _0037 (header ap dung cho bo phan)
            ho, _ = HeaderOrganization.objects.update_or_create(
                org_id=org_id,
                header_registration=hr,
                defaults={
                    "registered_by": user,
                    "approved_by": user,
                    "type": HeaderRegistration.TypeChoices.NO_REGISTRATION,
                    "is_selected": True,
                    "status": hr.status,
                },
            )

            # _0036: user dang ky header
            UserHeaderRegistration.objects.update_or_create(
                registered_by=user,
                header_registration=hr,
                defaults={
                    "approved_by": user,
                    "status": HeaderRegistration.StatusChoices.APPROVED,
                },
            )

            # _0038: user chon header organization nay
            HeaderOrganizationUserRegistration.objects.update_or_create(
                registered_by=user,
                header_organization=ho,
                defaults={
                    "approved_by": user,
                    "is_selected": True,
                    "status": HeaderRegistration.StatusChoices.APPROVED,
                },
            )

        # _0039 + _0040: quyen he thong cho tung SystemHeader co power
        for header in headers:
            for power in SystemPower.objects.filter(system_header_id=header.id).order_by("sort", "id"):
                perm, _ = SystemPermission.objects.update_or_create(
                    org_id=org_id,
                    power_id=power.id,
                    defaults={
                        "registered_by": user,
                        "approved_by": user,
                        "type": HeaderRegistration.TypeChoices.NO_REGISTRATION,
                        "status": HeaderRegistration.StatusChoices.APPROVED,
                    },
                )
                UserSystemPermissionRegistration.objects.update_or_create(
                    registered_by=user,
                    system_permission=perm,
                    defaults={
                        "approved_by": user,
                        "status": HeaderRegistration.StatusChoices.APPROVED,
                    },
                )

        self.stdout.write(f"  Registered {len(registrations)} header(s) for org {org_id}")

    def handle(self, *args, **options):
        if options["clean"]:
            # Xóa theo thứ tự con -> cha để tránh lỗi FK / PROTECT
            UserSystemPermissionRegistration.objects.all().delete()
            SystemPermission.objects.all().delete()
            HeaderOrganizationUserRegistration.objects.all().delete()
            HeaderOrganization.objects.all().delete()
            UserHeaderRegistration.objects.all().delete()
            HeaderRegistration.objects.all().delete()
            User.objects.all().delete()
            SystemPower.objects.all().delete()
            SystemHeader.objects.all().delete()
            PagesHeader.objects.all().delete()
            GroupHeader.objects.all().delete()
            Material.objects.all().delete()
            Vendor.objects.all().delete()
            Organization.objects.all().delete()
            Shift.objects.all().delete()
            self.stdout.write(self.style.WARNING("Deleted all existing seed data"))

        self._seed_organizations()
        self._seed_shifts()
        self._seed_vendors()
        self._seed_materials()
        self._seed_group_headers()
        self._seed_pages_headers()
        self._seed_system_headers()
        self._seed_system_powers()
        user = self._seed_user()
        self._seed_registrations(user)

        self.stdout.write(self.style.SUCCESS("Seeded all example data successfully!"))
        self.stdout.write(
            f"  Organizations: {Organization.objects.count()} | "
            f"Shifts: {Shift.objects.count()} | "
            f"Vendors: {Vendor.objects.count()} | "
            f"Materials: {Material.objects.count()}"
        )
        self.stdout.write(
            f"  GroupHeaders: {GroupHeader.objects.count()} | "
            f"PagesHeaders: {PagesHeader.objects.count()} | "
            f"SystemHeaders: {SystemHeader.objects.count()} | "
            f"SystemPowers: {SystemPower.objects.count()}"
        )
        self.stdout.write(
            f"  HeaderRegistrations: {HeaderRegistration.objects.count()} | "
            f"UserHeaderRegs: {UserHeaderRegistration.objects.count()} | "
            f"HeaderOrganizations: {HeaderOrganization.objects.count()} | "
            f"HeaderOrgUserRegs: {HeaderOrganizationUserRegistration.objects.count()} | "
            f"SystemPermissions: {SystemPermission.objects.count()} | "
            f"UserSystemPermRegs: {UserSystemPermissionRegistration.objects.count()}"
        )
        self.stdout.write(
            f"  User: {user.gen_id} / {user.full_name} "
            f"(password: 'Luongka97*' — login bằng gen_id hoặc knox_id 'luong97.duc')"
        )