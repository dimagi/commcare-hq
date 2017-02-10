from django.test import SimpleTestCase
from corehq.apps.users.custom_data import _get_invalid_user_data_fields
from corehq.apps.users.models import CommCareUser


class RemoveUnusedFieldsTestCase(SimpleTestCase):

    def test_empty(self):
        user_with_no_fields = CommCareUser(user_data={})
        self.assertEqual([], _get_invalid_user_data_fields(user_with_no_fields, set()))
        self.assertEqual([], _get_invalid_user_data_fields(user_with_no_fields, set(['a', 'b'])))

    def test_normal_behavior(self):
        user_with_fields = CommCareUser(user_data={'a': 'foo', 'b': 'bar', 'c': 'baz'})
        self.assertEqual(set(['a', 'b', 'c']), set(_get_invalid_user_data_fields(user_with_fields, set())))
        self.assertEqual(set(['c']), set(_get_invalid_user_data_fields(user_with_fields, set(['a', 'b']))))
        self.assertEqual(set(['a', 'b', 'c']),
                         set(_get_invalid_user_data_fields(user_with_fields, set(['e', 'f']))))

    def test_system_fields_not_removed(self):
        user_with_system_fields = CommCareUser(user_data={'commcare_location_id': 'foo'})
        self.assertEqual([], _get_invalid_user_data_fields(user_with_system_fields, set()))
        self.assertEqual([], _get_invalid_user_data_fields(user_with_system_fields, set(['a', 'b'])))
