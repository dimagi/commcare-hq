from django.contrib.postgres.fields import ArrayField
from django.db import models

from corehq.apps.users.landing_pages import ALL_LANDING_PAGES
from corehq.util.models import ForeignValue, foreign_value_init
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.couch.migration import SyncSQLToCouchMixin


class SQLUserRole(SyncSQLToCouchMixin, models.Model):
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

    class Meta:
        db_table = "users_userrole"
        indexes = (
            models.Index(fields=("domain",)),
            models.Index(fields=("couch_id",)),
        )

    @classmethod
    def _migration_get_fields(cls):
        return [
            "domain",
            "name",
            "default_landing_page",
            "is_non_admin_editable",
            "is_archived",
            "upstream_id",
        ]

    @classmethod
    def _migration_get_couch_model_class(cls):
        from corehq.apps.users.models import UserRole
        return UserRole

    def _migration_sync_submodels_to_couch(self, couch_object):
        couch_object.permissions = self.permissions
        couch_object.assignable_by = self.assignable_by

    @property
    def get_id(self):
        assert self.couch_id is not None
        return self.couch_id

    def get_qualified_id(self):
        return 'user-role:%s' % self.get_id

    def set_permissions(self, permission_infos):
        self.rolepermission_set.set([
            RolePermission.from_permission_info(self, info)
            for info in permission_infos
        ], bulk=False)

    def get_permission_infos(self):
        return [rp.as_permission_info() for rp in self.rolepermission_set.all()]

    @property
    def permissions(self):
        from corehq.apps.users.models import Permissions
        return Permissions.from_permission_list(self.get_permission_infos())

    def get_assignable_by(self):
        return list(self.roleassignableby_set.select_related("assignable_by_role").all())

    @property
    def assignable_by(self):
        return list(
            self.roleassignableby_set.values_list('assignable_by_role__couch_id', flat=True)
        )


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
        constraints = [
            models.CheckConstraint(
                name="users_rolepermission_valid_allow",
                check=~models.Q(allow_all=True, allowed_items__len__gt=0)
            )
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
    sql_role.rolepermission_set.all().delete()
    sql_role.set_permissions(user_role.permissions.to_list())


def migrate_role_assignable_by_to_sql(couch_role, sql_role):
    from corehq.apps.users.models import UserRole

    assignments_by_role_id = {
        assignment.assignable_by_role.get_id: assignment
        for assignment in sql_role.get_assignable_by()
    }
    removed = set(assignments_by_role_id) - set(couch_role.assignable_by)
    for role_id in removed:
        assignments_by_role_id[role_id].delete()

    added = set(couch_role.assignable_by) - set(assignments_by_role_id)
    for doc in iter_docs(UserRole.get_db(), added):
        couch_role = UserRole.wrap(doc)
        assignable_by_role = couch_role._migration_get_sql_object()  # noqa
        if not assignable_by_role:
            assignable_by_role = couch_role._migration_do_sync()  # noqa
            assert assignable_by_role is not None

        sql_role.roleassignableby_set.add(
            RoleAssignableBy(role=sql_role, assignable_by_role=assignable_by_role), bulk=False
        )
