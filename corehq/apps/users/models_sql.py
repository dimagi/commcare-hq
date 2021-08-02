import attr
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import FieldDoesNotExist
from django.db import models, transaction

from corehq.apps.users.landing_pages import ALL_LANDING_PAGES
from corehq.util.models import ForeignValue, foreign_value_init
from dimagi.utils.couch.migration import SyncSQLToCouchMixin, disable_sync_to_couch


@attr.s(frozen=True)
class StaticRole:
    domain = attr.ib()
    name = attr.ib()
    permissions = attr.ib()
    default_landing_page = None
    is_non_admin_editable = False
    is_archived = False
    upstream_id = None
    couch_id = None
    assignable_by = []

    @classmethod
    def domain_admin(cls, domain):
        from corehq.apps.users.models import Permissions
        return StaticRole(domain, "Admin", Permissions.max())

    @classmethod
    def domain_default(cls, domain):
        from corehq.apps.users.models import Permissions
        return StaticRole(domain, None, Permissions())

    def get_qualified_id(self):
        return self.name.lower() if self.name else None

    @property
    def get_id(self):
        return None

    @property
    def cache_version(self):
        return self.name

    def to_json(self):
        return role_to_dict(self)


class UserRoleManager(models.Manager):

    def get_by_domain(self, domain, include_archived=False):
        query = self.filter(domain=domain)
        if not include_archived:
            query = query.filter(is_archived=False)
        return list(query.prefetch_related('rolepermission_set'))

    def by_domain_and_name(self, domain, name):
        # name is not unique so return all results
        return list(self.filter(domain=domain, name=name))

    def by_couch_id(self, couch_id, domain=None):
        if domain:
            query = SQLUserRole.objects.filter(domain=domain)
        else:
            query = SQLUserRole.objects
        return query.get(couch_id=couch_id)


class SQLUserRole(models.Model):
    domain = models.CharField(max_length=128, null=True)
    name = models.CharField(max_length=128, null=True)
    default_landing_page = models.CharField(
        max_length=64, choices=[(page.id, page.name) for page in ALL_LANDING_PAGES], null=True
    )
    # role can be assigned by all non-admins
    is_non_admin_editable = models.BooleanField(null=False, default=False)
    is_archived = models.BooleanField(null=False, default=False)
    upstream_id = models.CharField(max_length=32, null=True)
    couch_id = models.CharField(max_length=126, null=True)

    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)

    objects = UserRoleManager()

    class Meta:
        db_table = "users_userrole"
        indexes = (
            models.Index(fields=("domain",)),
            models.Index(fields=("couch_id",)),
        )

    @classmethod
    def create(cls, domain, name, permissions=None, assignable_by=None, **kwargs):
        from corehq.apps.users.models import Permissions
        with transaction.atomic():
            role = SQLUserRole.objects.create(domain=domain, name=name, **kwargs)
            if permissions is None:
                # match couch functionality and set default permissions
                permissions = Permissions()
            role.set_permissions(permissions.to_list())
            if assignable_by:
                if not isinstance(assignable_by, list):
                    assignable_by = [assignable_by]
                role.set_assignable_by(assignable_by)

        return role

    @property
    def get_id(self):
        assert self.couch_id is not None
        return self.couch_id

    def get_qualified_id(self):
        return 'user-role:%s' % self.get_id

    @property
    def cache_version(self):
        return self.modified_on.isoformat()

    def to_json(self):
        return role_to_dict(self)

    @transaction.atomic
    def set_permissions(self, permission_infos):
        def _clear_cache_sync_with_couch():
            try:
                self.refresh_from_db(fields=["rolepermission_set"])
            except FieldDoesNotExist:
                pass

        if not permission_infos:
            RolePermission.objects.filter(role=self).delete()
            _clear_cache_sync_with_couch()
            return

        permissions_by_name = {
            rp.permission: rp
            for rp in self.rolepermission_set.all()
        }
        for info in permission_infos:
            perm = permissions_by_name.pop(info.name, None)
            if not perm:
                new_perm = RolePermission.from_permission_info(self, info)
                new_perm.save()
            elif (perm.allow_all, perm.allowed_items) != (info.allow_all, info.allowed_items):
                perm.allow_all = info.allow_all
                perm.allowed_items = info.allowed_items
                perm.save()

        if permissions_by_name:
            old_ids = [old.id for old in permissions_by_name.values()]
            RolePermission.objects.filter(id__in=old_ids).delete()

        _clear_cache_sync_with_couch()

    def get_permission_infos(self):
        return [rp.as_permission_info() for rp in self.rolepermission_set.all()]

    @property
    def permissions(self):
        from corehq.apps.users.models import Permissions
        return Permissions.from_permission_list(self.get_permission_infos())

    def set_assignable_by_couch(self, couch_role_ids):
        sql_ids = []
        if couch_role_ids:
            sql_ids = SQLUserRole.objects.filter(couch_id__in=couch_role_ids).values_list('id', flat=True)
        self.set_assignable_by(sql_ids)

    @transaction.atomic
    def set_assignable_by(self, role_ids):
        def _clear_cache_sync_with_couch():
            try:
                self.refresh_from_db(fields=["roleassignableby_set"])
            except FieldDoesNotExist:
                pass

        if not role_ids:
            self.roleassignableby_set.all().delete()
            _clear_cache_sync_with_couch()
            return

        assignments_by_role_id = {
            assignment[0]: assignment[1]
            for assignment in self.roleassignableby_set.values_list('assignable_by_role_id', 'id').all()
        }

        for role_id in role_ids:
            assignment = assignments_by_role_id.pop(role_id, None)
            if not assignment:
                assignment = RoleAssignableBy(role=self, assignable_by_role_id=role_id)
                assignment.save()

        if assignments_by_role_id:
            old_ids = list(assignments_by_role_id.values())
            RoleAssignableBy.objects.filter(id__in=old_ids).delete()

        _clear_cache_sync_with_couch()

    def get_assignable_by(self):
        return list(self.roleassignableby_set.select_related("assignable_by_role").all())

    @property
    def assignable_by_sql(self):
        return list(
            self.roleassignableby_set.values_list('assignable_by_role_id', flat=True)
        )

    @property
    def assignable_by_couch(self):
        return list(
            self.roleassignableby_set.values_list('assignable_by_role__couch_id', flat=True)
        )

    @property
    def assignable_by(self):
        # alias for compatibility with couch UserRole
        return self.assignable_by_couch

    def accessible_by_non_admin_role(self, role_id):
        return self.is_non_admin_editable or (role_id and role_id in self.assignable_by)


@foreign_value_init
class RolePermission(models.Model):
    role = models.ForeignKey("SQLUserRole", on_delete=models.CASCADE)
    permission_fk = models.ForeignKey("SQLPermission", on_delete=models.CASCADE)
    permission = ForeignValue(permission_fk)

    # if True allow access to all items
    # if False only allow access to listed items
    allow_all = models.BooleanField(default=True)

    # current max len in 119 chars
    allowed_items = ArrayField(models.CharField(max_length=256), blank=True, null=True)

    class Meta:
        unique_together = [
            ("role", "permission_fk")
        ]
        constraints = [
            models.CheckConstraint(
                name="users_rolepermission_valid_allow",
                check=~models.Q(allow_all=True, allowed_items__len__gt=0)
            ),
        ]

    @staticmethod
    def from_permission_info(role, info):
        return RolePermission(
            role=role, permission=info.name, allow_all=info.allow_all, allowed_items=info.allowed_items
        )

    def as_permission_info(self):
        from corehq.apps.users.models import PermissionInfo
        allow = PermissionInfo.ALLOW_ALL if self.allow_all else self.allowed_items
        return PermissionInfo(self.permission, allow=allow)


class SQLPermission(models.Model):
    value = models.CharField(max_length=255, unique=True)

    class Meta:
        db_table = "users_permission"

    @classmethod
    def create_all(cls):
        from corehq.apps.users.models import Permissions
        for name in Permissions.permission_names():
            SQLPermission.objects.get_or_create(value=name)


class RoleAssignableBy(models.Model):
    role = models.ForeignKey("SQLUserRole", on_delete=models.CASCADE)
    assignable_by_role = models.ForeignKey(
        "SQLUserRole", on_delete=models.CASCADE, related_name="can_assign_roles"
    )


def migrate_role_permissions_to_sql(user_role, sql_role):
    sql_role.set_permissions(user_role.permissions.to_list())


def migrate_role_assignable_by_to_sql(couch_role, sql_role):
    from corehq.apps.users.models import UserRole

    assignable_by_mapping = {
        ids[0]: ids[1] for ids in
        SQLUserRole.objects.filter(couch_id__in=couch_role.assignable_by).values_list('couch_id', 'id')
    }
    if len(assignable_by_mapping) != len(couch_role.assignable_by):
        for couch_id in couch_role.assignable_by:
            if couch_id not in assignable_by_mapping:
                assignable_by_sql_role = UserRole.get(couch_id)._migration_do_sync()  # noqa
                assert assignable_by_sql_role is not None
                assignable_by_mapping[couch_id] = assignable_by_sql_role.id

    sql_role.set_assignable_by(list(assignable_by_mapping.values()))


def role_to_dict(role):
    data = {}
    for field in SQLUserRole._migration_get_fields():
        data[field] = getattr(role, field)
    data["permissions"] = role.permissions.to_json()
    data["assignable_by"] = role.assignable_by
    if role.couch_id:
        data["_id"] = role.couch_id
    return data
