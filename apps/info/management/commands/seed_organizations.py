from django.core.management.base import BaseCommand

from apps.info.models import Material, Organization, Shift, Vendor


class Command(BaseCommand):
    help = "Seed all info data (Organization, Shift, Vendor, Material)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Delete existing data before seeding",
        )

    def _seed_organizations(self):
        data = [
            # id, parent_id, name, sort, is_use
            (1, None, "SEVT", 1, True),
            (2, 1, "SET QC Team", 1, True),
            (3, 2, "IQC G", 1, True),
            (4, 3, "IQC 1P", 1, True),
            (5, 3, "IQC 2P", 2, True),
            (6, 3, "IQC 3P", 3, True),
            (11, 4, "System", 1, True),
            (12, 4, "CKD / SKD", 2, True),
            (13, 4, "Semi", 3, True),
            (14, 4, "Reliability (DTC)", 4, True),
            (15, 4, "Inno MEC", 5, True),
            (21, 5, "Inno MEC", 1, True),
            (22, 5, "Incoming MEC", 2, True),
            (23, 5, "Trouble MEC", 3, True),
            (24, 5, "RMA MEC", 4, True),
            (25, 5, "New Model", 5, True),
            (31, 6, "Inno ELE", 1, True),
            (32, 6, "Incoming ELE", 2, True),
            (33, 6, "Trouble ELE", 3, True),
            (34, 6, "RMA ELE", 4, True),
        ]
        for org_id, pid, name, sort, is_use in data:
            Organization.objects.update_or_create(
                id=org_id,
                defaults={
                    "name": name,
                    "sort": sort,
                    "is_use": is_use,
                    "parent_id": pid,
                },
            )

    def _seed_shifts(self):
        data = [
            (1, "Hành chính", "Staff A1", "Staff A1"),
            (2, "Shift 1", "Shift 1A1", "Shift 1A1"),
            (3, "Shift 2", "Shift 2A1", "Shift 2A1"),
        ]
        for sid, vi, en, kr in data:
            Shift.objects.update_or_create(
                id=sid,
                defaults={
                    "shift_vi": vi,
                    "shift_en": en,
                    "shift_kr": kr,
                },
            )

    def _seed_vendors(self):
        data = [
            # vendor_code, vendor_name, is_use, is_replace
        ]
        for vcode, vname, is_use, is_replace in data:
            Vendor.objects.update_or_create(
                vendor_code=vcode,
                defaults={
                    "vendor_name": vname,
                    "is_use": is_use,
                    "is_replace": is_replace,
                },
            )

    def _seed_materials(self):
        data = [
            # material_code, model, model_full, part_name, part_name_full, color, group, is_manual
        ]
        for mcode, model, model_full, pname, pname_full, color, group, is_manual in data:
            Material.objects.update_or_create(
                material_code=mcode,
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

    def handle(self, *args, **options):
        if options["clean"]:
            Organization.objects.all().delete()
            Shift.objects.all().delete()
            Vendor.objects.all().delete()
            Material.objects.all().delete()
            self.stdout.write(self.style.WARNING("Deleted existing info data"))

        self._seed_organizations()
        self._seed_shifts()
        self._seed_vendors()
        self._seed_materials()

        self.stdout.write(self.style.SUCCESS("Seeded info data successfully!"))
        self.stdout.write(
            f"  Organizations: {Organization.objects.count()} | "
            f"Shifts: {Shift.objects.count()} | "
            f"Vendors: {Vendor.objects.count()} | "
            f"Materials: {Material.objects.count()}"
        )