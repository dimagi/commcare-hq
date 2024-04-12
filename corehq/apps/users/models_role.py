import uuid

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import FieldDoesNotExist
from django.db import models, transaction

import attr
from field_audit import audit_fields
from field_audit.models import AuditAction, AuditingManager

from dimagi.utils.logging import notify_error

from corehq.apps.users.landing_pages import ALL_LANDING_PAGES
from corehq.util.models import ForeignValue, foreign_init


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
    is_commcare_user_default = False

    @classmethod
    def domain_admin(cls, domain):
        from corehq.apps.users.models import HqPermissions
        return StaticRole(domain, "Admin", HqPermissions.max())

    @classmethod
    def domain_default(cls, domain):
        from corehq.apps.users.models import HqPermissions
        return StaticRole(domain, None, HqPermissions())

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


class UserRoleManager(AuditingManager):

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
            query = UserRole.objects.filter(domain=domain)
        else:
            query = UserRole.objects
        return query.get(couch_id=couch_id)


def _uuid_str():
    return uuid.uuid4().hex


@audit_fields("domain", "name", "default_landing_page", "is_non_admin_editable",
              "is_archived", "upstream_id", "couch_id",
              "is_commcare_user_default", audit_special_queryset_writes=True)
class UserRole(models.Model):
    domain = models.CharField(max_length=128, null=True)
    name = models.CharField(max_length=128, null=True)
    default_landing_page = models.CharField(
        max_length=64,
        choices=[(page.id, page.name) for page in ALL_LANDING_PAGES],
        null=True,
    )
    # role can be assigned by all non-admins
    is_non_admin_editable = models.BooleanField(null=False, default=False)
    is_archived = models.BooleanField(null=False, default=False)
    upstream_id = models.CharField(max_length=32, null=True)
    couch_id = models.CharField(max_length=126, null=True, default=_uuid_str)
    is_commcare_user_default = models.BooleanField(null=True, default=False)

    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)

    objects = UserRoleManager()

    class Meta:
        db_table = "users_userrole"
        indexes = (
            models.Index(fields=("domain",)),
            models.Index(fields=("couch_id",)),
        )

    def __repr__(self):
        return f"UserRole(domain='{self.domain}', name='{self.name}')"

    @classmethod
    def create(cls, domain, name, permissions=None, assignable_by=None, **kwargs):
        from corehq.apps.users.models import HqPermissions
        with transaction.atomic():
            role = UserRole.objects.create(domain=domain, name=name, **kwargs)
            if permissions is None:
                # match couch functionality and set default permissions
                permissions = HqPermissions()
            role.set_permissions(permissions.to_list())
            if assignable_by:
                if not isinstance(assignable_by, list):
                    assignable_by = [assignable_by]
                role.set_assignable_by(assignable_by)

        return role

    @classmethod
    def commcare_user_default(cls, domain):
        """This will get the default mobile worker role for the domain. If one does not exist it
        will create a new role.

        Note: the role should exist for all domains but errors during domain registration can leave
        domains improperly configured."""
        from corehq.apps.users.role_utils import UserRolePresets
        role, created = UserRole.objects.get_or_create(domain=domain, is_commcare_user_default=True, defaults={
            "name": UserRolePresets.MOBILE_WORKER
        })
        if created:
            notify_error("Domain was missing default commcare user role", {
                "domain": domain
            })
            permissions = UserRolePresets.INITIAL_ROLES[UserRolePresets.MOBILE_WORKER]()
            role.set_permissions(permissions.to_list())
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
        def _clear_query_cache():
            try:
                # There is a bug in refresh_from_db when specifying fields that results in this error:
                # RuntimeError: Set changed size during iteration
                # Once on a version of Django that includes the change made for
                # https://code.djangoproject.com/ticket/35044, we can specify fields again.
                # self.refresh_from_db(fields=["rolepermission_set"])
                self.refresh_from_db()
            except FieldDoesNotExist:
                pass

        if not permission_infos:
            RolePermission.objects.filter(role=self).delete(audit_action=AuditAction.AUDIT)
            _clear_query_cache()
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
            RolePermission.objects.filter(id__in=old_ids).delete(audit_action=AuditAction.AUDIT)

        _clear_query_cache()

    def get_permission_infos(self):
        return [rp.as_permission_info() for rp in self.rolepermission_set.all()]

    @property
    def permissions(self):
        from corehq.apps.users.models import HqPermissions
        return HqPermissions.from_permission_list(self.get_permission_infos())

    def set_assignable_by_couch(self, couch_role_ids):
        sql_ids = []
        if couch_role_ids:
            sql_ids = UserRole.objects.filter(couch_id__in=couch_role_ids).values_list('id', flat=True)
        self.set_assignable_by(sql_ids)

    @transaction.atomic
    def set_assignable_by(self, role_ids):
        def _clear_query_cache():
            try:
                # There is a bug in refresh_from_db when specifying fields that results in this error:
                # RuntimeError: Set changed size during iteration
                # Once on a version of Django that includes the change made for
                # https://code.djangoproject.com/ticket/35044, we can specify fields again.
                # self.refresh_from_db(fields=["roleassignableby_set"])
                self.refresh_from_db()
            except FieldDoesNotExist:
                pass

        if not role_ids:
            self.roleassignableby_set.all().delete(audit_action=AuditAction.AUDIT)
            _clear_query_cache()
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
            RoleAssignableBy.objects.filter(id__in=old_ids).delete(audit_action=AuditAction.AUDIT)

        _clear_query_cache()

    def get_assignable_by(self):
        return list(self.roleassignableby_set.select_related("assignable_by_role").all())

    @property
    def assignable_by_couch(self):
        return list(self.roleassignableby_set.values_list("assignable_by_role__couch_id", flat=True))

    @property
    def assignable_by(self):
        # alias for compatibility with couch UserRole
        return self.assignable_by_couch

    def accessible_by_non_admin_role(self, role_id):
        return self.is_non_admin_editable or (role_id and role_id in self.assignable_by)


@audit_fields("role", "permission_fk", "allow_all", "allowed_items",
              audit_special_queryset_writes=True)
@foreign_init
class RolePermission(models.Model):
    role = models.ForeignKey("UserRole", on_delete=models.CASCADE)
    permission_fk = models.ForeignKey("Permission", on_delete=models.CASCADE)
    permission = ForeignValue(permission_fk)

    # if True allow access to all items
    # if False only allow access to listed items
    allow_all = models.BooleanField(default=True)

    # current max len in 119 chars
    allowed_items = ArrayField(models.CharField(max_length=256), blank=True, null=True)

    objects = AuditingManager()

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

    def __repr__(self):
        return f"RolePermission(role={self.role}, permission='{self.permission}')"

    @staticmethod
    def from_permission_info(role, info):
        return RolePermission(
            role=role, permission=info.name, allow_all=info.allow_all, allowed_items=info.allowed_items
        )

    def as_permission_info(self):
        from corehq.apps.users.models import PermissionInfo
        allow = PermissionInfo.ALLOW_ALL if self.allow_all else self.allowed_items
        return PermissionInfo(self.permission, allow=allow)


class PermissionManager(AuditingManager):

    def get_by_natural_key(self, value):
        # Useful when serializing data that foreign keys to this table for a migration (e.g., RolePermission)
        return self.get(value=value)


@audit_fields("value", audit_special_queryset_writes=True)
class Permission(models.Model):
    value = models.CharField(max_length=255, unique=True)

    objects = PermissionManager()

    class Meta:
        db_table = "users_permission"

    def __repr__(self):
        return f"Permission('{self.value}')"

    @classmethod
    def create_all(cls):
        from corehq.apps.users.models import HqPermissions
        for name in HqPermissions.permission_names():
            Permission.objects.get_or_create(value=name)

    def natural_key(self):
        # Useful when serializing data that foreign keys to this table for a migration (e.g., RolePermission)
        return (self.value,)


@audit_fields("role", "assignable_by_role", audit_special_queryset_writes=True)
class RoleAssignableBy(models.Model):
    role = models.ForeignKey("UserRole", on_delete=models.CASCADE)
    assignable_by_role = models.ForeignKey(
        "UserRole", on_delete=models.CASCADE, related_name="can_assign_roles"
    )
    objects = AuditingManager()


def role_to_dict(role):
    simple_fields = [
        "domain",
        "name",
        "default_landing_page",
        "is_non_admin_editable",
        "is_archived",
        "upstream_id",
        "is_commcare_user_default"
    ]
    data = {}
    for field in simple_fields:
        data[field] = getattr(role, field)
    data["permissions"] = role.permissions.to_json()
    data["assignable_by"] = role.assignable_by
    if role.couch_id:
        data["_id"] = role.couch_id
    return data
