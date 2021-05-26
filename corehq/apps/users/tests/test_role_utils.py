from django.test import TestCase

from corehq.apps.users.models import UserRole, Permissions
from corehq.apps.users.role_utils import get_or_create_role_with_permissions


class RoleUtilsTests(TestCase):
    domain = 'role-utils'

    @classmethod
    def setUpTestData(cls):
        cls.role1_permissions = Permissions(edit_web_users=True)
        cls.role1 = UserRole.create(cls.domain, 'role1', permissions=cls.role1_permissions)

    @classmethod
    def tearDownClass(cls):
        for role in UserRole.by_domain(cls.domain):
            role.delete()
        super().tearDownClass()

    def test_get_or_create_role_with_permissions_create(self):
        permissions = Permissions(view_web_users=True)
        role = get_or_create_role_with_permissions(self.domain, 'new_role', permissions)
        self.assertNotEqual(role.get_id, self.role1.get_id)
        self.assertEqual(role.name, 'new_role')

    def test_get_or_create_role_with_permissions_get_existing(self):
        role = get_or_create_role_with_permissions(self.domain, 'new_role', self.role1_permissions)
        self.assertEqual(role.get_id, self.role1.get_id)
        self.assertEqual(role.name, 'role1')
