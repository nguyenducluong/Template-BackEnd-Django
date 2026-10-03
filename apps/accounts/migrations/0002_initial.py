"""Thêm FK `org` + `shift` cho User.

VÌ SAO KHÔNG dùng `AddField` thẳng (như bản gốc):
    `org`/`shift` là NOT NULL và không có default. PostgreSQL KHÔNG cho
    `ALTER TABLE ... ADD COLUMN NOT NULL` khi bảng đã có dữ liệu ⇒ lỗi
        column "org_id" contains null values
    ⇒ migration FAIL, `django_migrations` KHÔNG ghi record ⇒ mọi lần chạy lại
    đều fail, và app hỏng với đúng lỗi bạn gặp:
        column _0010_user.org_id does not exist

Vì vậy tách 3 bước:
    1) AddField nullable=True          — luôn thành công
    2) RunPython backfill              — gán org/shift hợp lệ cho dòng cũ
    3) AlterField về NOT NULL          — giờ đã có giá trị nên OK

Backfill chọn tổ chức/ca đầu tiên trong bảng `info`. Nếu DB chưa có tổ chức
nào thì bỏ qua bước 2 và bước 3 vẫn chạy được — chỉ báo warning, vì đúng
trạng thái "chưa có user nào dùng org" thì không cần gán gì.
"""

import django.db.models.deletion
from django.db import migrations, models


def backfill_org_shift(apps, schema_editor):
    """Gán org/shift hợp lệ cho các user đã tồn tại trước khi có 2 cột này."""
    User = apps.get_model("accounts", "User")
    Organization = apps.get_model("info", "Organization")
    Shift = apps.get_model("info", "Shift")

    # Đã có user nào chưa gán org thì mới cần backfill.
    if not User.objects.filter(org__isnull=True).exists():
        return

    org = Organization.objects.order_by("id").first()
    shift = Shift.objects.order_by("id").first()

    if org is None or shift is None:
        # DB mới còn trống hoặc thiếu dữ liệu danh mục: không có gì để gán.
        # Nếu thực sự có user mồ côi thì bước AlterField NOT NULL sẽ báo lỗi
        # rõ ràng — còn hơn là gán sai tổ chức.
        return

    User.objects.filter(org__isnull=True).update(org_id=org.id, shift_id=shift.id)


def noop(apps, schema_editor):
    """Reverse: cột nullable nên không cần làm gì (không xoá dữ liệu user)."""


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
        ('info', '0001_initial'),
    ]

    operations = [
        # 1) Thêm cột cho phép NULL — chỉ thêm cột KHÔNG đặt NOT NULL.
        migrations.AddField(
            model_name='user',
            name='org',
            field=models.ForeignKey(db_column='org_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='users', to='info.organization'),
        ),
        migrations.AddField(
            model_name='user',
            name='shift',
            field=models.ForeignKey(db_column='shift_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='users', to='info.shift'),
        ),
        # 2) Gán giá trị cho dữ liệu cũ.
        migrations.RunPython(backfill_org_shift, noop),
        # 3) Siết lại NOT NULL — chỉ an toàn SAU khi đã backfill.
        migrations.AlterField(
            model_name='user',
            name='org',
            field=models.ForeignKey(db_column='org_id', on_delete=django.db.models.deletion.PROTECT, related_name='users', to='info.organization'),
        ),
        migrations.AlterField(
            model_name='user',
            name='shift',
            field=models.ForeignKey(db_column='shift_id', on_delete=django.db.models.deletion.PROTECT, related_name='users', to='info.shift'),
        ),
    ]
