from django.test import TestCase

from corehq.apps.users.models import PermissionInfo, Permissions
from corehq.apps.users.models_sql import SQLUserRole, SQLPermission, RolePermission, RoleAssignableBy


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

        cls.roles[0].set_permissions([
            PermissionInfo(Permissions.edit_data.name),
        ])
        cls.roles[0].set_assignable_by([cls.roles[1].id])

    @classmethod
    def tearDownClass(cls):
        SQLUserRole.objects.all().delete()
        super().tearDownClass()

    def test_get_by_domain(self):
        domain_roles = {role.name: role for role in SQLUserRole.by_domain(self.domain)}
        self.assertDictEqual({"role1": self.roles[0], "role2": self.roles[1]}, domain_roles)

    def test_set_permissions(self):
        role = SQLUserRole(
            domain=self.domain,
            name="test-role",
        )
        role.save()
        role.rolepermission_set.set([
            RolePermission(permission=Permissions.edit_data.name),
            RolePermission(permission=Permissions.manage_releases.name, allow_all=False, allowed_items=['app1']),
            RolePermission(permission=Permissions.view_reports.name, allow_all=True),
        ], bulk=False)

        self.assertEqual(set(role.get_permission_infos()), {
            PermissionInfo(Permissions.edit_data.name),
            PermissionInfo(Permissions.manage_releases.name, allow=['app1']),
            PermissionInfo(Permissions.view_reports.name, allow=PermissionInfo.ALLOW_ALL),
        })

        new_permissions = {
            # removed edit_data
            PermissionInfo(Permissions.access_api.name),  # new
            PermissionInfo(Permissions.edit_data.name, allow=['app1', 'app2']),  # edit
            PermissionInfo(Permissions.view_reports.name, allow=['report1']),  # edit
        }
        role.set_permissions(new_permissions)

        role2 = SQLUserRole.objects.get(id=role.id)
        self.assertEqual(set(role2.get_permission_infos()), new_permissions)

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
