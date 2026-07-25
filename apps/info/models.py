from django.db import models


class Organization(models.Model):
    id = models.BigAutoField(primary_key=True)

    # Khóa ngoại tự tham chiếu (Self-referential Foreign Key)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        db_column='parent_id'
    )

    name = models.CharField(max_length=100)
    level = models.PositiveSmallIntegerField(
        choices=[
            (0, "Team"),
            (1, "Group"),
            (2, "Part"),
            (3, "Location"),
        ],
        default=0,
    )
    sort = models.IntegerField(default=0)
    is_use = models.BooleanField(default=False)

    # ---- Cached hierarchy (Phase 2a - denormalized for performance) ----
    # These are computed on save and via signals when parent changes.
    cached_full_path = models.CharField(
        max_length=255, null=True, blank=True, db_index=True,
        help_text="Denormalized: '1.2.4.22.'",
    )
    cached_full_name = models.CharField(
        max_length=500, null=True, blank=True,
        help_text="Denormalized: 'SET QC Team => IQC G => ...'",
    )

    # ------------------------------------------------------------------
    # Hierarchy helpers (equivalent to view_0002_organizations full_path)
    # ------------------------------------------------------------------
    def _compute_hierarchy(self):
        """Compute full_path and full_name by walking up the tree."""
        parts, names, node, seen = [], [], self, set()
        while node is not None and node.id not in seen:
            seen.add(node.id)
            parts.append(str(node.id))
            names.append(node.name)
            node = node.parent
        return ".".join(reversed(parts)) + ".", " => ".join(reversed(names))

    def save(self, *args, **kwargs):
        """Save and update cached hierarchy fields."""
        super().save(*args, **kwargs)
        # Recompute after save (need self.id)
        path, name = self._compute_hierarchy()
        if self.cached_full_path != path or self.cached_full_name != name:
            self.cached_full_path = path
            self.cached_full_name = name
            # Use update to avoid recursion and signals
            Organization.objects.filter(pk=self.pk).update(
                cached_full_path=path, cached_full_name=name
            )

    @property
    def full_path(self) -> str:
        """e.g. '1.2.4.22.' — id chain from root to this node."""
        if self.cached_full_path:
            return self.cached_full_path
        path, _ = self._compute_hierarchy()
        return path

    @property
    def full_name(self) -> str:
        """e.g. 'SET QC Team => IQC G => IQC 2P => Incoming MEC'."""
        if self.cached_full_name:
            return self.cached_full_name
        _, name = self._compute_hierarchy()
        return name

    class Meta:
        db_table = '_0000_organizations'
        ordering = ['sort', 'id']
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'

    def __str__(self):
        return self.name


class Shift(models.Model):
    id = models.BigAutoField(primary_key=True)
    shift_vi = models.CharField(max_length=25)
    shift_en = models.CharField(max_length=25)
    shift_kr = models.CharField(max_length=25)

    class Meta:
        db_table = '_0006_shift'
        ordering = ['id']
        verbose_name = 'Shift'
        verbose_name_plural = 'Shifts'

    def __str__(self):
        return self.shift_vi


class Vendor(models.Model):
    vendor_code = models.CharField(max_length=15, primary_key=True)
    vendor_name = models.CharField(max_length=125)
    is_use = models.BooleanField(default=True)
    is_replace = models.BooleanField(default=False)

    class Meta:
        db_table = '_0020_info_vendor'
        ordering = ['vendor_code']
        verbose_name = 'Vendor'
        verbose_name_plural = 'Vendors'

    def __str__(self):
        return f"{self.vendor_code} - {self.vendor_name}"


class Material(models.Model):
    material_code = models.CharField(max_length=11, primary_key=True)
    model = models.CharField(max_length=8, null=True, blank=True)
    model_full = models.CharField(max_length=15, null=True, blank=True)
    part_name = models.CharField(max_length=50)
    part_name_full = models.CharField(max_length=125)
    color = models.CharField(max_length=25, null=True, blank=True)
    group = models.IntegerField()
    is_manual = models.BooleanField(default=False)

    class Meta:
        db_table = '_0021_info_material'
        ordering = ['material_code']
        verbose_name = 'Material'
        verbose_name_plural = 'Materials'

    def __str__(self):
        return f"{self.material_code} - {self.part_name}"


class GroupHeader(models.Model):
    id = models.BigAutoField(primary_key=True)
    sort = models.PositiveSmallIntegerField(default=1)
    is_use = models.BooleanField(default=True)
    group_vi = models.CharField(max_length=25)
    group_en = models.CharField(max_length=25)
    group_kr = models.CharField(max_length=25)

    class Meta:
        db_table = '_0030_group_header'
        ordering = ['sort', 'id']
        verbose_name = 'Group Header'
        verbose_name_plural = 'Group Headers'

    def __str__(self):
        return self.group_vi


class PagesHeader(models.Model):
    id = models.BigAutoField(primary_key=True)
    group_header = models.ForeignKey(
        GroupHeader,
        on_delete=models.CASCADE,
        related_name='pages',
        db_column='group_header_id',
    )
    is_use = models.BooleanField(default=True)
    sort = models.PositiveSmallIntegerField(default=1)
    page_vi = models.CharField(max_length=50)
    page_en = models.CharField(max_length=50)
    page_kr = models.CharField(max_length=50)

    class Meta:
        db_table = '_0031_pages_header'
        ordering = ['sort', 'id']
        verbose_name = 'Pages Header'
        verbose_name_plural = 'Pages Headers'

    def __str__(self):
        return self.page_vi


class SystemHeader(models.Model):
    id = models.BigAutoField(primary_key=True)
    page_header = models.ForeignKey(
        PagesHeader,
        on_delete=models.CASCADE,
        related_name='system_headers',
        db_column='page_header_id',
    )
    sort = models.PositiveSmallIntegerField(default=1)
    is_use = models.BooleanField(default=True)
    is_mobile = models.BooleanField(default=False)
    view_vi = models.CharField(max_length=75)
    view_en = models.CharField(max_length=75)
    view_kr = models.CharField(max_length=75)
    header_vi = models.CharField(max_length=75)
    header_en = models.CharField(max_length=75)
    header_kr = models.CharField(max_length=75)

    class Meta:
        db_table = '_0032_system_header'
        ordering = ['sort', 'id']
        verbose_name = 'System Header'
        verbose_name_plural = 'System Headers'

    def __str__(self):
        return self.header_vi


class SystemPower(models.Model):
    id = models.BigAutoField(primary_key=True)
    system_header = models.ForeignKey(
        SystemHeader,
        on_delete=models.CASCADE,
        related_name='powers',
        db_column='system_header_id',
    )
    is_use = models.BooleanField(default=True)
    sort = models.PositiveSmallIntegerField(default=1)
    power_vi = models.CharField(max_length=75)
    power_en = models.CharField(max_length=75)
    power_kr = models.CharField(max_length=75)

    class Meta:
        db_table = '_0033_system_power'
        ordering = ['sort', 'id']
        verbose_name = 'System Power'
        verbose_name_plural = 'System Powers'

    def __str__(self):
        return self.power_vi


class HeaderRegistration(models.Model):
    """`_0035` — Đăng ký header cho bộ phận (organization).

    FK được thiết kế lại: giữ unique (org, header) nhưng các bảng con sẽ
    tham chiếu qua surrogate `id` thay vì composite (org_id, header_id).
    """

    class TypeChoices(models.IntegerChoices):
        NEED_REGISTRATION = 0, "Cần đăng ký"
        NO_REGISTRATION = 1, "Không cần đăng ký"

    class StatusChoices(models.IntegerChoices):
        PENDING = 0, "Pending Approval"
        APPROVED = 1, "Approval"
        REJECTED = 2, "Rejected"

    id = models.BigAutoField(primary_key=True)
    crt_at = models.DateTimeField(auto_now_add=True)
    registered_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="header_registrations",
        db_column="rgt_id",
    )
    org = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="header_registrations",
        db_column="org_id",
    )
    header = models.ForeignKey(
        SystemHeader,
        on_delete=models.CASCADE,
        related_name="registrations",
        db_column="header_id",
    )

    approved_at = models.DateTimeField(null=True, blank=True, db_column="apr_at")
    approved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="header_registrations_approved",
        db_column="apr_id",
    )
    type = models.PositiveSmallIntegerField(
        choices=TypeChoices.choices, default=TypeChoices.NEED_REGISTRATION
    )
    status = models.PositiveSmallIntegerField(
        choices=StatusChoices.choices, default=StatusChoices.PENDING
    )

    class Meta:
        db_table = "_0035_header_registration"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["org", "header"], name="uq_0035_org_header"
            )
        ]
        verbose_name = "Header Registration"
        verbose_name_plural = "Header Registrations"

    def __str__(self):
        return f"{self.org} -> {self.header} ({self.get_status_display()})"


class UserHeaderRegistration(models.Model):
    """`_0036` — Người dùng đăng ký header trong bộ phận.

    Thiết kế lại: FK đơn `header_registration` (tới `_0035.id`) thay cho
    composite (org_id, header_id).
    """

    class StatusChoices(models.IntegerChoices):
        PENDING = 0, "Pending Approval"
        APPROVED = 1, "Approval"
        REJECTED = 2, "Rejected"

    id = models.BigAutoField(primary_key=True)
    crt_at = models.DateTimeField(auto_now_add=True)
    registered_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="user_header_registrations",
        db_column="rgt_id",
    )
    header_registration = models.ForeignKey(
        HeaderRegistration,
        on_delete=models.CASCADE,
        related_name="user_registrations",
        db_column="header_registration_id",
    )

    approved_at = models.DateTimeField(null=True, blank=True, db_column="apr_at")
    approved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="user_header_registrations_approved",
        db_column="apr_id",
    )
    status = models.PositiveSmallIntegerField(
        choices=StatusChoices.choices, default=StatusChoices.PENDING
    )

    class Meta:
        db_table = "_0036_user_header_registration"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["registered_by", "header_registration"],
                name="uq_0036_user_header_registration",
            )
        ]
        verbose_name = "User Header Registration"
        verbose_name_plural = "User Header Registrations"

    def __str__(self):
        return (
            f"{self.registered_by_id} -> {self.header_registration_id} "
            f"({self.get_status_display()})"
        )


class HeaderOrganization(models.Model):
    """`_0037` — Header áp dụng cho người dùng trong bộ phận.

    Thiết kế lại: FK đơn `header_registration` (tới `_0035.id`) thay cho
    composite (org_rgt_id, header_id); `org` là bộ phận của người dùng.
    """

    class TypeChoices(models.IntegerChoices):
        NEED_REGISTRATION = 0, "Cần đăng ký"
        NO_REGISTRATION = 1, "Không cần đăng ký"

    class StatusChoices(models.IntegerChoices):
        PENDING = 0, "Pending Approval"
        APPROVED = 1, "Approval"
        REJECTED = 2, "Rejected"

    id = models.BigAutoField(primary_key=True)
    crt_at = models.DateTimeField(auto_now_add=True)
    registered_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="header_organizations",
        db_column="rgt_id",
    )
    org = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="header_organizations",
        db_column="org_id",
    )
    header_registration = models.ForeignKey(
        HeaderRegistration,
        on_delete=models.CASCADE,
        related_name="organization_assignments",
        db_column="header_registration_id",
    )

    approved_at = models.DateTimeField(null=True, blank=True, db_column="apr_at")
    approved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="header_organizations_approved",
        db_column="apr_id",
    )
    type = models.PositiveSmallIntegerField(
        choices=TypeChoices.choices, default=TypeChoices.NEED_REGISTRATION
    )
    is_selected = models.BooleanField(default=False)
    status = models.PositiveSmallIntegerField(
        choices=StatusChoices.choices, default=StatusChoices.PENDING
    )

    class Meta:
        db_table = "_0037_header_organizations"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["org", "header_registration"],
                name="uq_0037_org_header_registration",
            )
        ]
        verbose_name = "Header Organization"
        verbose_name_plural = "Header Organizations"

    def __str__(self):
        return f"{self.org} <- {self.header_registration}"


class HeaderOrganizationUserRegistration(models.Model):
    """`_0038` — Bộ phận đăng ký header với từng gen_id (người dùng).

    Thiết kế lại: FK đơn `header_organization` (tới `_0037.id`) thay cho
    composite (org_id, org_rgt_id, header_id).
    """

    class StatusChoices(models.IntegerChoices):
        PENDING = 0, "Pending Approval"
        APPROVED = 1, "Approval"
        REJECTED = 2, "Rejected"

    id = models.BigAutoField(primary_key=True)
    crt_at = models.DateTimeField(auto_now_add=True)
    registered_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="header_org_user_registrations",
        db_column="rgt_id",
    )
    header_organization = models.ForeignKey(
        HeaderOrganization,
        on_delete=models.CASCADE,
        related_name="user_registrations",
        db_column="header_organization_id",
    )

    approved_at = models.DateTimeField(null=True, blank=True, db_column="apr_at")
    approved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="header_org_user_registrations_approved",
        db_column="apr_id",
    )
    is_selected = models.BooleanField(default=False)
    status = models.PositiveSmallIntegerField(
        choices=StatusChoices.choices, default=StatusChoices.PENDING
    )

    class Meta:
        db_table = "_0038_header_organization_user_registration"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["registered_by", "header_organization"],
                name="uq_0038_user_header_organization",
            )
        ]
        verbose_name = "Header Organization User Registration"
        verbose_name_plural = "Header Organization User Registrations"

    def __str__(self):
        return (
            f"{self.registered_by_id} -> {self.header_organization_id} "
            f"({self.get_status_display()})"
        )

class SystemPermission(models.Model):
    """`_0039` — Đăng ký quyền hệ thống cho bộ phận (tương tự `_0035`).

    FK đơn `power` tới `_0033_system_power`; unique (org, power) giữ nguyên
    để các bảng con tham chiếu qua surrogate `id`.
    """

    class TypeChoices(models.IntegerChoices):
        NEED_REGISTRATION = 0, "Cần đăng ký"
        NO_REGISTRATION = 1, "Không cần đăng ký"

    class StatusChoices(models.IntegerChoices):
        PENDING = 0, "Pending Approval"
        APPROVED = 1, "Approval"
        REJECTED = 2, "Rejected"

    id = models.BigAutoField(primary_key=True)
    crt_at = models.DateTimeField(auto_now_add=True)
    registered_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="system_permissions",
        db_column="rgt_id",
    )
    org = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="system_permissions",
        db_column="org_id",
    )
    power = models.ForeignKey(
        SystemPower,
        on_delete=models.CASCADE,
        related_name="permissions",
        db_column="power_id",
    )

    approved_at = models.DateTimeField(null=True, blank=True, db_column="apr_at")
    approved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="system_permissions_approved",
        db_column="apr_id",
    )
    type = models.PositiveSmallIntegerField(
        choices=TypeChoices.choices, default=TypeChoices.NEED_REGISTRATION
    )
    status = models.PositiveSmallIntegerField(
        choices=StatusChoices.choices, default=StatusChoices.PENDING
    )

    class Meta:
        db_table = "_0039_system_permissions"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["org", "power"], name="uq_0039_org_power"
            )
        ]
        verbose_name = "System Permission"
        verbose_name_plural = "System Permissions"

    def __str__(self):
        return f"{self.org} -> {self.power} ({self.get_status_display()})"


class UserSystemPermissionRegistration(models.Model):
    """`_0040` — Người dùng đăng ký quyền hệ thống (tương tự `_0036`).

    Thiết kế lại: FK đơn `system_permission` (tới `_0039.id`) thay cho
    composite (org_id, power_id).
    """

    class StatusChoices(models.IntegerChoices):
        PENDING = 0, "Pending Approval"
        APPROVED = 1, "Approval"
        REJECTED = 2, "Rejected"

    id = models.BigAutoField(primary_key=True)
    crt_at = models.DateTimeField(auto_now_add=True)
    registered_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="user_system_permission_registrations",
        db_column="rgt_id",
    )
    system_permission = models.ForeignKey(
        SystemPermission,
        on_delete=models.CASCADE,
        related_name="user_registrations",
        db_column="system_permission_id",
    )

    approved_at = models.DateTimeField(null=True, blank=True, db_column="apr_at")
    approved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="user_system_permission_registrations_approved",
        db_column="apr_id",
    )
    status = models.PositiveSmallIntegerField(
        choices=StatusChoices.choices, default=StatusChoices.PENDING
    )

    class Meta:
        db_table = "_0040_user_system_permissions_registration"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["registered_by", "system_permission"],
                name="uq_0040_user_system_permission",
            )
        ]
        verbose_name = "User System Permission Registration"
        verbose_name_plural = "User System Permission Registrations"

    def __str__(self):
        return (
            f"{self.registered_by_id} -> {self.system_permission_id} "
            f"({self.get_status_display()})"
        )
