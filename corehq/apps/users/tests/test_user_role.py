from django.db import IntegrityError
from django.db.transaction import atomic
from django.test import TestCase

from corehq.apps.users.models import (
    Permissions,
    SQLUserRole, SQLPermission, RolePermission, RoleAssignableBy, PermissionInfo
)


class RolesTests(TestCase):
    domain = "test-roles"

    @classmethod
    def setUpTestData(cls):
        SQLPermission.create_all()
        cls.roles = [
            SQLUserRole(
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

        cls.roles[0].set_permissions([
            PermissionInfo(Permissions.edit_data.name),
        ])

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

    def test_set_permissions(self):
        role = SQLUserRole(
            domain=self.domain,
            name="test-role",
        )
        role.save()
        role.rolepermission_set.set([
            RolePermission(permission=Permissions.edit_data.name),
            RolePermission(permission=Permissions.view_reports.name, allow_all=False,
                           allowed_items=['report1']),
        ], bulk=False)

        self.assertEqual(set(role.get_permission_infos()), {
            PermissionInfo(Permissions.edit_data.name),
            PermissionInfo(Permissions.view_reports.name, allow=['report1']),
        })

        new_permissions = {
            # removed edit_data
            PermissionInfo(Permissions.access_api.name),  # new
            PermissionInfo(Permissions.view_reports.name, allow=['report1', 'report2']),  # edit
        }
        role.set_permissions(new_permissions)

        role2 = SQLUserRole.objects.get(id=role.id)
        self.assertEqual(set(role2.get_permission_infos()), new_permissions)

        # change parameterized permission to allow all
        new_permissions = {
            PermissionInfo(Permissions.view_reports.name, allow=PermissionInfo.ALLOW_ALL),  # edit
        }
        role.set_permissions(new_permissions)

        role2 = SQLUserRole.objects.get(id=role.id)
        self.assertEqual(set(role2.get_permission_infos()), new_permissions)


class TestRolePermissionsModel(TestCase):
    domain = "user-role-test"

    def setUp(self):
        self.role1 = SQLUserRole(domain=self.domain, name="role1")
        self.role1.save()
        self.addCleanup(self.role1.delete)


    def _test_allow_check_constraint(self, name, allow_all, allowed_items):
        self.role1.rolepermission_set.set([
            RolePermission(permission=name, allow_all=allow_all, allowed_items=allowed_items)
        ], bulk=False)

    def test_allow_check_constraint_allow_all_params_none(self):
        self._test_allow_check_constraint(Permissions.view_reports.name, True, None)

    def test_allow_check_constraint_allow_all_params_empty(self):
        self._test_allow_check_constraint(Permissions.view_reports.name, True, [])

    def test_allow_check_constraint_params_list(self):
        self._test_allow_check_constraint(Permissions.view_reports.name, False, ['report1'])

    @atomic
    def test_allow_check_constraint_fail(self):
        constraint_name = "users_rolepermission_valid_allow"
        with self.assertRaisesMessage(IntegrityError, constraint_name):
            self.role1.rolepermission_set.set([
                RolePermission(permission=Permissions.view_reports.name, allow_all=True, allowed_items=['report1']),
            ], bulk=False)

    def test_unique_constraint_ok(self):
        self.role1.rolepermission_set.set([
            RolePermission(permission=Permissions.edit_data.name, allow_all=True),
        ], bulk=False)

        role2 = SQLUserRole(domain=self.domain, name="role2")
        role2.save()
        self.addCleanup(role2.delete)

        role2.rolepermission_set.set([
            RolePermission(permission=Permissions.edit_data.name, allow_all=True),
        ], bulk=False)

    @atomic
    def test_unique_constraint_fail(self):
        sql_role = SQLUserRole(domain=self.domain, name="role1")
        sql_role.save()
        self.addCleanup(sql_role.delete)

        constraint_name = "users_rolepermission_role_id_permission_fk_id_bc5f84db_uniq"
        with self.assertRaisesMessage(IntegrityError, constraint_name):
            sql_role.rolepermission_set.set([
                RolePermission(permission=Permissions.edit_data.name, allow_all=True),
                RolePermission(permission=Permissions.edit_data.name, allow_all=False),
            ], bulk=False)
