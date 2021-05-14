from django.db import IntegrityError
from django.db.transaction import atomic
from django.test import TestCase

from corehq.apps.users.models import (
    Permissions,
    SQLUserRole, SQLPermission, RolePermission, RoleAssignableBy
)


class RolesTests(TestCase):
    domain = "test-roles"

    @classmethod
    def setUpTestData(cls):
        SQLPermission.create_all()
        cls.roles = [SQLUserRole(
                domain=cls.domain,
                name="role1",
            ),
            SQLUserRole(
                domain=cls.domain,
                name="role2",
            ),
            SQLUserRole(
                domain='other-domain',
                name="role3",
            )
        ]
        for role in cls.roles:
            role.save()

        cls.roles[0].set_assignable_by([cls.roles[1].id])

    @classmethod
    def tearDownClass(cls):
        SQLUserRole.objects.all().delete()
        super().tearDownClass()

    def test_set_assignable_by(self):
        role = SQLUserRole(
            domain=self.domain,
            name="test-role",
        )
        role.save()

        role.roleassignableby_set.set([
            RoleAssignableBy(assignable_by_role=self.roles[0]),
            RoleAssignableBy(assignable_by_role=self.roles[1]),
        ], bulk=False)

        self.assertEqual({a.assignable_by_role.name for a in role.get_assignable_by()}, {
            self.roles[0].name, self.roles[1].name
        })

        # remove 1, keep 1, add 1
        new_assignments = {
            self.roles[1],
            self.roles[2]
        }
        role.set_assignable_by([r.id for r in new_assignments])

        role2 = SQLUserRole.objects.get(id=role.id)
        self.assertEqual(
            {a.assignable_by_role.name for a in role2.get_assignable_by()},
            {r.name for r in new_assignments}
        )


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
