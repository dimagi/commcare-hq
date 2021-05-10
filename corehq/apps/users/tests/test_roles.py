from django.test import TestCase

from corehq.apps.users.models import PermissionInfo, Permissions
from corehq.apps.users.models_sql import SQLUserRole, SQLPermission


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
        cls.roles[0].set_assignable_by([cls.roles[1]])

    @classmethod
    def tearDownClass(cls):
        SQLUserRole.objects.all().delete()
        super().tearDownClass()

    def test_get_by_domain(self):
        domain_roles = {role.name: role for role in SQLUserRole.by_domain(self.domain)}
        self.assertDictEqual({"role1": self.roles[0], "role2": self.roles[1]}, domain_roles)
