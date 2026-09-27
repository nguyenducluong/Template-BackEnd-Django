from django.core.management.base import BaseCommand

from apps.info.models import Material, Organization, Shift, Vendor

# LevelChoices lay truc tiep tu model de seed dung chung choices voi DB
LevelChoices = Organization.LevelChoices


class Command(BaseCommand):
    help = "Seed all info data (Organization, Shift, Vendor, Material)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Delete existing data before seeding",
        )

    def _seed_organizations(self):
        # id, parent_id, name, level, sort, is_use
        # level dung Organization.LevelChoices:
        #   0 Company - 1 Team - 2 Group - 3 Part - 4 Location
        data = [
            (1, None, "SEVT", LevelChoices.COMPANY, 1, True),
            (2, 1, "SET QC Team", LevelChoices.TEAM, 1, True),
            (3, 2, "IQC G", LevelChoices.TEAM, 1, True),
            (4, 3, "IQC 1P", LevelChoices.GROUP, 1, True),
            (5, 3, "IQC 2P", LevelChoices.GROUP, 2, True),
            (6, 3, "IQC 3P", LevelChoices.GROUP, 3, True),
            (11, 4, "System", LevelChoices.PART, 1, True),
            (12, 4, "CKD / SKD", LevelChoices.PART, 2, True),
            (13, 4, "Semi", LevelChoices.PART, 3, True),
            (14, 4, "Reliability (DTC)", LevelChoices.PART, 4, True),
            (15, 4, "Inno MEC", LevelChoices.PART, 5, True),
            (21, 5, "Inno MEC", LevelChoices.LOCATION, 1, True),
            (22, 5, "Incoming MEC", LevelChoices.LOCATION, 2, True),
            (23, 5, "Trouble MEC", LevelChoices.LOCATION, 3, True),
            (24, 5, "RMA MEC", LevelChoices.LOCATION, 4, True),
            (25, 5, "New Model", LevelChoices.LOCATION, 5, True),
            (31, 6, "Inno ELE", LevelChoices.LOCATION, 1, True),
            (32, 6, "Incoming ELE", LevelChoices.LOCATION, 2, True),
            (33, 6, "Trouble ELE", LevelChoices.LOCATION, 3, True),
            (34, 6, "RMA ELE", LevelChoices.LOCATION, 4, True),
        ]
        for org_id, pid, name, level, sort, is_use in data:
            Organization.objects.update_or_create(
                id=org_id,
                defaults={
                    "name": name,
                    "level": level,
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