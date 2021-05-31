from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _

import jsonobject
from jsonfield.fields import JSONField

from dimagi.utils.couch.migration import SyncSQLToCouchMixin

from corehq.apps.users.landing_pages import ALL_LANDING_PAGES
from corehq.util.models import ForeignValue, foreign_value_init


class UserRoleManager(models.Manager):

    def by_couch_id(self, couch_id):
        return SQLUserRole.objects.get(couch_id=couch_id)


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

    objects = UserRoleManager()

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
        couch_object.assignable_by = list(
            self.roleassignableby_set.values_list('assignable_by_role__couch_id', flat=True)
        )

    @property
    def get_id(self):
        assert self.couch_id is not None
        return self.couch_id

    def get_qualified_id(self):
        return 'user-role:%s' % self.get_id

    def set_permissions(self, permission_infos):
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

    def get_permission_infos(self):
        return [rp.as_permission_info() for rp in self.rolepermission_set.all()]

    @property
    def permissions(self):
        from corehq.apps.users.models import Permissions
        return Permissions.from_permission_list(self.get_permission_infos())

    def set_assignable_by(self, role_ids):
        if not role_ids:
            self.roleassignableby_set.all().delete()
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

    def get_assignable_by(self):
        return list(self.roleassignableby_set.select_related("assignable_by_role").all())

    @property
    def assignable_by(self):
        return list(
            self.roleassignableby_set.values_list('assignable_by_role_id', flat=True)
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


class UserUpdateMeta(jsonobject.JsonObject):
    updated_via = jsonobject.StringProperty()


class UpdateDetails(jsonobject.JsonObject):
    meta = jsonobject.ObjectProperty(UserUpdateMeta)
    changes = jsonobject.DictProperty()


class HQLogEntry(models.Model):
    """
    HQ Adaptation of Django's LogEntry model
    """
    CREATE = 1
    UPDATE = 2
    DELETE = 3

    ACTION_FLAG_CHOICES = (
        (CREATE, _('Create')),
        (UPDATE, _('Update')),
        (DELETE, _('Delete')),
    )
    domain = models.CharField(max_length=255, db_index=True, null=True)
    object_type = models.CharField(max_length=255, db_index=True, choices=(
        ('CommCareUser', 'CommCareUser'),
        ('WebUser', 'WebUser'),
    ))
    object_id = models.CharField(max_length=128, db_index=True)
    by_user_id = models.CharField(max_length=128, db_index=True)
    details = JSONField(default=dict)  # UpdateDetails
    message = models.TextField(_('change message'), blank=True)
    action_time = models.DateTimeField(_('action time'), auto_now_add=True, editable=False)
    action_flag = models.PositiveSmallIntegerField(_('action flag'), choices=ACTION_FLAG_CHOICES)


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
