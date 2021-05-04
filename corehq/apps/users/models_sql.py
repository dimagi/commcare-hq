from django.contrib.postgres.fields import ArrayField
from django.db import models

from corehq.apps.users.landing_pages import ALL_LANDING_PAGES
from corehq.util.models import ForeignValue
from dimagi.utils.couch.migration import SyncSQLToCouchMixin


class SQLUserRole(SyncSQLToCouchMixin, models.Model):
    domain = models.CharField(max_length=128, null=True, db_index=True)
    name = models.CharField(max_length=128, null=True)
    default_landing_page = models.CharField(
        max_length=12, choices=[(page.id, page.name) for page in ALL_LANDING_PAGES], null=True
    )
    is_non_admin_editable = models.BooleanField(null=False, default=False)
    is_archived = models.BooleanField(null=False, default=False)
    upstream_id = models.CharField(max_length=32, null=True)
    permissions = models.ManyToManyField("SQLPermission", through="RolePermission")
    couch_id = models.CharField(max_length=126, null=True, db_index=True)

    class Meta:
        db_table = "users_userrole"

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
        # TODO: permissions
        # TODO: assignable_by
        pass


class RolePermission(models.Model):
    role = models.ForeignKey("SQLUserRole", on_delete=models.CASCADE)
    permission_fk = models.ForeignKey("SQLPermission", on_delete=models.CASCADE)
    permission = ForeignValue(permission_fk)
    # current max len in 119 chars
    allowed_items = ArrayField(models.CharField(max_length=256), blank=True, null=True)


class SQLPermission(models.Model):
    value = models.CharField(max_length=255, db_index=True, unique=True)


class RoleAssignableBy(models.Model):
    role = models.ForeignKey("SQLUserRole", on_delete=models.CASCADE)
    assignable_by_role = models.ForeignKey("SQLUserRole", on_delete=models.CASCADE, related_name="assignable_by")
