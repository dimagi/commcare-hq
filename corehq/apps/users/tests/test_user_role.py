from unittest.mock import Mock

from django.db import IntegrityError
from django.db.transaction import atomic
from django.test import TestCase, SimpleTestCase

from corehq.apps.users.models import (
    Permissions,
    UserRole, SQLPermission, RolePermission, RoleAssignableBy, PermissionInfo,
    StaticRole
)


class RolesTests(TestCase):
    domain = "test-roles"

    @classmethod
    def setUpTestData(cls):
        SQLPermission.create_all()
        cls.roles = [
            UserRole(
                domain=cls.domain,
                name="role1",
            ),
            UserRole(
                domain=cls.domain,
                name="role2",
            ),
            UserRole(
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

    def test_set_assignable_by(self):
        role = UserRole(
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

        role2 = UserRole.objects.get(id=role.id)
        self.assertEqual(
            {a.assignable_by_role.name for a in role2.get_assignable_by()},
            {r.name for r in new_assignments}
        )

    def test_set_assignable_by_clear_prefetched_cache(self):
        role = UserRole.create(
            domain=self.domain,
            name="test-role",
            assignable_by=[self.roles[0].id]
        )
        self.assertEqual({a.assignable_by_role.name for a in role.get_assignable_by()}, {
            self.roles[0].name
        })

        new_assignments = {
            self.roles[2]
        }
        role_with_prefetch = UserRole.objects.prefetch_related("roleassignableby_set").get(id=role.id)
        role_with_prefetch.set_assignable_by([r.id for r in new_assignments])

        self.assertEqual(
            {a.assignable_by_role.name for a in role_with_prefetch.roleassignableby_set.all()},
            {r.name for r in new_assignments}
        )

        role_with_prefetch = UserRole.objects.prefetch_related("roleassignableby_set").get(id=role.id)
        role_with_prefetch.set_assignable_by([])
        self.assertEqual(list(role_with_prefetch.roleassignableby_set.all()), [])

    def test_set_assignable_by_couch(self):
        role = UserRole(
            domain=self.domain,
            name="test-role",
        )
        role.save()

        new_assignments = {
            self.roles[1],
            self.roles[2]
        }
        role.set_assignable_by_couch([r.couch_id for r in new_assignments])

        role2 = UserRole.objects.get(id=role.id)
        self.assertEqual(
            {a.assignable_by_role.name for a in role2.get_assignable_by()},
            {r.name for r in new_assignments}
        )

    def test_set_permissions(self):
        role = UserRole(
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

        role2 = UserRole.objects.get(id=role.id)
        self.assertEqual(set(role2.get_permission_infos()), new_permissions)

        # change parameterized permission to allow all
        new_permissions = {
            PermissionInfo(Permissions.view_reports.name, allow=PermissionInfo.ALLOW_ALL),  # edit
        }
        role.set_permissions(new_permissions)

        role2 = UserRole.objects.get(id=role.id)
        self.assertEqual(set(role2.get_permission_infos()), new_permissions)

    def test_set_permissions_clear_prefetch_cache(self):
        role = UserRole.create(
            domain=self.domain,
            name="test-role",
            permissions=Permissions()
        )

        self.assertEqual(set(role.get_permission_infos()), set(Permissions().to_list()))

        role_with_prefetch = UserRole.objects.prefetch_related("rolepermission_set").get(id=role.id)
        new_permissions = {PermissionInfo(Permissions.access_api.name)}
        role_with_prefetch.set_permissions(new_permissions)

        self.assertEqual(set(role_with_prefetch.get_permission_infos()), new_permissions)

        role_with_prefetch = UserRole.objects.prefetch_related("rolepermission_set").get(id=role.id)
        role_with_prefetch.set_permissions([])
        self.assertEqual(list(role_with_prefetch.get_permission_infos()), [])

    def test_by_couch_id(self):
        role = UserRole.objects.by_couch_id(self.roles[0].get_id)
        self.assertEqual(role.id, self.roles[0].id)

        role = UserRole.objects.by_couch_id(self.roles[0].get_id, domain=self.roles[0].domain)
        self.assertEqual(role.id, self.roles[0].id)

        with self.assertRaises(UserRole.DoesNotExist):
            UserRole.objects.by_couch_id(self.roles[0].get_id, domain="other-domain")

    def test_create_atomic(self):
        sql_roles_in_domain = {role.get_id for role in self.roles[0:2]}

        permissions_raises_exception = Mock(side_effect=Exception)
        with self.assertRaises(Exception):
            UserRole.create(self.domain, 'test_atomic', permissions=permissions_raises_exception)

        # check sql role not created
        sql_roles = UserRole.objects.get_by_domain(self.domain)
        self.assertEqual({role.get_id for role in sql_roles}, sql_roles_in_domain)


class TestRolePermissionsModel(TestCase):
    domain = "user-role-test"

    def setUp(self):
        self.role1 = UserRole(domain=self.domain, name="role1")
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
        """different roles can have the same permission"""
        self.role1.rolepermission_set.set([
            RolePermission(permission=Permissions.edit_data.name, allow_all=True),
        ], bulk=False)

        role2 = UserRole(domain=self.domain, name="role2")
        role2.save()
        self.addCleanup(role2.delete)

        role2.rolepermission_set.set([
            RolePermission(permission=Permissions.edit_data.name, allow_all=True),
        ], bulk=False)

    @atomic
    def test_unique_constraint_fail(self):
        """the same role can not have duplicate permissions"""
        sql_role = UserRole(domain=self.domain, name="role1")
        sql_role.save()
        self.addCleanup(sql_role.delete)

        constraint_name = "users_rolepermission_role_id_permission_fk_id_bc5f84db_uniq"
        with self.assertRaisesMessage(IntegrityError, constraint_name):
            sql_role.rolepermission_set.set([
                RolePermission(permission=Permissions.edit_data.name, allow_all=True),
                RolePermission(permission=Permissions.edit_data.name, allow_all=False),
            ], bulk=False)


class TestStaticRoles(SimpleTestCase):
    domain = "static-role-test"

    expected_role_dict = {
        "domain": "static-role-test",
        "name": None,
        "permissions": None,
        "default_landing_page": None,
        "is_non_admin_editable": False,
        "assignable_by": [],
        "is_archived": False,
        "upstream_id": None
    }

    def test_static_role_default(self):
        static_dict = StaticRole.domain_default(self.domain).to_json()
        expected = self.expected_role_dict.copy()
        expected["permissions"] = Permissions().to_json()
        self.assertDictEqual(expected, static_dict)

    def test_static_role_admin(self):
        static_admin_role = StaticRole.domain_admin(self.domain)
        expected = self.expected_role_dict.copy()
        expected["name"] = "Admin"
        expected["permissions"] = Permissions.max().to_json()
        self.assertDictEqual(expected, static_admin_role.to_json())
        self.assertEqual(static_admin_role.get_qualified_id(), "admin")
