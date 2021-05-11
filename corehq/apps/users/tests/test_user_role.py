from django.db import IntegrityError
from django.db.transaction import atomic
from django.test import TestCase

from corehq.apps.users.models import Permissions
from corehq.apps.users.models_sql import SQLUserRole, RolePermission


class TestRolePermissionsModel(TestCase):
    domain = "user-role-test"

    def test_allow_check_constraint_success(self):
        sql_role = SQLUserRole(domain=self.domain, name="role1")
        sql_role.save()
        self.addCleanup(sql_role.delete)

        sql_role.rolepermission_set.set([
            RolePermission(permission=Permissions.view_web_apps.name, allow_all=True, allowed_items=None),
            RolePermission(permission=Permissions.manage_releases.name, allow_all=True, allowed_items=[]),
            RolePermission(permission=Permissions.view_reports.name, allow_all=False, allowed_items=['report1']),
        ], bulk=False)

    @atomic
    def test_allow_check_constraint_fail(self):
        sql_role = SQLUserRole(domain=self.domain, name="role1")
        sql_role.save()
        self.addCleanup(sql_role.delete)

        constraint_name = "users_rolepermission_valid_allow"
        with self.assertRaisesMessage(IntegrityError, constraint_name):
            sql_role.rolepermission_set.set([
                RolePermission(permission=Permissions.view_reports.name, allow_all=True, allowed_items=['report1']),
            ], bulk=False)
