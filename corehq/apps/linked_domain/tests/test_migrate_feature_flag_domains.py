from django.test import TestCase
from django_prbac.models import Role, Grant

from corehq.apps.linked_domain.management.commands.migrate_feature_flag_domains import _update_roles_in_place, \
    _get_or_create_role_with_privilege


class UpdateRolesInPlaceTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.privilege_role = Role.objects.create(slug='privilege', name='test privilege')

    def test_successful_update(self):
        role = Role.objects.create(slug='role', name='test role')

        _update_roles_in_place([role.slug], self.privilege_role.slug)

        try:
            Grant.objects.get(from_role=role, to_role=self.privilege_role)
        except Grant.DoesNotExist:
            self.fail(f"Grant not found for {role.slug} and {self.privilege_role.slug}")

    def test_dry_run(self):
        role = Role.objects.create(slug='role', name='test role')

        _update_roles_in_place([role.slug], self.privilege_role.slug, dry_run=True)

        with self.assertRaises(Grant.DoesNotExist):
            Grant.objects.get(from_role=role, to_role=self.privilege_role)

    def test_invalid_role(self):
        with self.assertRaises(Role.DoesNotExist):
            _update_roles_in_place(['unknown-role'], self.privilege_role.slug)

    def test_invalid_privilege_role(self):
        role = Role.objects.create(slug='role', name='test role')

        with self.assertRaises(Role.DoesNotExist):
            _update_roles_in_place([role.slug], 'unknown-role')

    def test_multiple_roles(self):
        role1 = Role.objects.create(slug='role1', name='test role 1')
        role2 = Role.objects.create(slug='role2', name='test role 2')

        _update_roles_in_place([role1.slug, role2.slug], self.privilege_role.slug)

        try:
            Grant.objects.get(from_role=role1, to_role=self.privilege_role)
        except Grant.DoesNotExist:
            self.fail(f"Grant not found for {role1.slug} and {self.privilege_role.slug}")

        try:
            Grant.objects.get(from_role=role2, to_role=self.privilege_role)
        except Grant.DoesNotExist:
            self.fail(f"Grant not found for {role2.slug} and {self.privilege_role.slug}")


class GetOrCreateRoleWithPrivilegeTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.privilege_role = Role.objects.create(slug='privilege', name='test privilege')
        self.existing_role = Role.objects.create(slug='role', name='Role')

    def test_returns_none_if_role_exists_but_does_not_have_privilege(self):
        Role.objects.create(slug='role_erm', name='Role (With ERM)')
        # no grant created to add privilege
        role = _get_or_create_role_with_privilege(self.existing_role.slug, self.privilege_role.slug)
        self.assertIsNone(role)

    def test_returns_existing_role_with_privilege(self):
        role_with_privilege = Role.objects.create(slug='role_erm', name='Role (With ERM)')
        Grant.objects.create(from_role=role_with_privilege, to_role=self.privilege_role)

        actual_role = _get_or_create_role_with_privilege(self.existing_role.slug, self.privilege_role.slug)
        self.assertEqual(actual_role.id, role_with_privilege.id)

    def test_returns_new_role(self):
        actual_role = _get_or_create_role_with_privilege(self.existing_role.slug, self.privilege_role.slug)
        self.assertEqual(actual_role.slug, 'role_erm')
        try:
            Grant.objects.get(from_role=actual_role, to_role=self.privilege_role)
        except Grant.DoesNotExist:
            self.fail(f"Grant not found for {actual_role.slug} and {self.privilege_role.slug}")
