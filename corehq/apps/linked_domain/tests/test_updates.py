from django.test import SimpleTestCase
from corehq.apps.users.models import UserRole
from corehq.apps.linked_domain.updates import _get_matching_downstream_entry, _copy_role_attributes


class UpdateUserRolesTests(SimpleTestCase):
    def test_get_downstream_entry_when_no_match_is_found_returns_none(self):
        upstream_entry = {'name': 'test', 'id': '7', '_id': '8'}
        downstream_entries = []
        result = _get_matching_downstream_entry(upstream_entry, downstream_entries)
        self.assertIsNone(result)

    def test_get_downstream_entry_matches_on_upstream_id(self):
        # upstream_entry = UserRole(name='test', id='7', couch_id='8')
        upstream_entry = {'name': 'test', 'id': '7', '_id': '8'}
        downstream_entries = [UserRole(name='test2', upstream_id='8')]
        result = _get_matching_downstream_entry(upstream_entry, downstream_entries)
        self.assertEqual(result.name, 'test2')

    def test_get_downstream_entry_does_not_match_on_name(self):
        # upstream_entry = UserRole(name='test', couch_id='8')
        upstream_entry = {'name': 'test', '_id': '8'}
        downstream_entries = [UserRole(name='test')]
        result = _get_matching_downstream_entry(upstream_entry, downstream_entries)
        self.assertIsNone(result)


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
