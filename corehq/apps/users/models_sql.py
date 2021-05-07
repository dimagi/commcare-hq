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
        self._migrate_permissions_to_couch(couch_object)
        self._migrate_assignable_by_to_couch(couch_object)

    def _migrate_permissions_to_couch(self, couch_object):
        couch_object.permissions = self.permissions

    def _migrate_assignable_by_to_couch(self, couch_object):
        couch_object.assignable_by = self.assignable_by

    @property
    def get_id(self):
        assert self.couch_id is not None
        return self.couch_id

    def get_qualified_id(self):
        return 'user-role:%s' % self.get_id

    def get_permissions(self):
        return [rp.as_permission() for rp in self.rolepermission_set.all()]

    @property
    def permissions(self):
        from corehq.apps.users.models import Permissions
        return Permissions.from_permission_list(self.get_permissions())

    def get_assignable_by(self):
        return list(self.roleassignableby_set.select_related("assignable_by_role").all())

    @property
    def assignable_by(self):
        return [
            assignment.assignable_by_role.get_id
            for assignment in self.get_assignable_by()
        ]


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

    def as_permission(self):
        from corehq.apps.users.models import Permission
        return Permission(self.permission, self.allow_all, self.allowed_items)


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
        "SQLUserRole", on_delete=models.CASCADE,related_name="can_assign_roles"
    )


def migrate_role_permissions_to_sql(user_role, sql_role):
    sql_permissions = []
    for couch_perm in user_role.permissions.to_list():
        sql_perm = RolePermission(
            role=sql_role,
            allow_all=couch_perm.allow_all,
            allowed_items=couch_perm.allowed_items
        )
        sql_perm.permission = couch_perm.name
        sql_permissions.append(sql_perm)
    sql_role.rolepermission_set.all().delete()
    sql_role.rolepermission_set.set(sql_permissions, bulk=False)


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
