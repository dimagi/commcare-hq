from django.test import SimpleTestCase
from corehq.apps.users.models import UserRole
from corehq.apps.linked_domain.updates import _copy_role_attributes


class RoleCopyTests(SimpleTestCase):
    def test_copy_role_attributes_populates_all_attributes(self):
        source_role = UserRole(
            name='test',
            default_landing_page='testpage',
            is_non_admin_editable=False,
        )

        dest_role = UserRole()

        _copy_role_attributes(source_role.to_json(), dest_role)

        self.assertEqual(dest_role.name, 'test')
        self.assertEqual(dest_role.default_landing_page, 'testpage')
        self.assertFalse(dest_role.is_non_admin_editable)

    def test_copy_role_preserves_destination_domain(self):
        source_role = UserRole(name='test', domain='source')
        dest_role = UserRole(domain='dest')

        _copy_role_attributes(source_role.to_json(), dest_role)
        self.assertEqual(dest_role.domain, 'dest')
