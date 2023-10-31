import uuid
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
)
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.user_data import SQLUserData, UserData, UserDataError
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView


class TestUserMetadata(TestCase):
    domain = 'test-user-metadata'

    def test_user_data_accessor(self):
        user = CommCareUser.create(self.domain, 'birdman', '***', None, None)
        self.addCleanup(user.delete, self.domain, deleted_by=None)
        user_data = user.get_user_data(self.domain)
        self.assertEqual(user_data['commcare_project'], self.domain)
        user_data.update({
            'cruise': 'control',
            'this': 'road',
        })
        # Normally you shouldn't use `user.user_data` directly - I'm demonstrating that it's updated
        self.assertEqual(user.user_data, {
            'cruise': 'control',
            'this': 'road',
        })
        del user_data['cruise']
        self.assertEqual(user.user_data, {
            'this': 'road',
        })
        user_data.update({'this': 'field'})
        self.assertEqual(user.user_data, {
            'this': 'field',
        })

    def test_web_users(self):
        # This behavior is bad - data isn't fully scoped to domain
        web_user = WebUser.create(None, "imogen", "*****", None, None)
        self.addCleanup(web_user.delete, self.domain, deleted_by=None)
        user_data = web_user.get_user_data(self.domain)
        self.assertEqual(user_data.to_dict(), {
            'commcare_project': self.domain,
            'commcare_profile': '',
        })

        user_data['start'] = 'sometimes'
        self.assertEqual(web_user.get_user_data(self.domain).to_dict(), {
            'commcare_project': self.domain,
            'commcare_profile': '',
            'start': 'sometimes',
        })
        self.assertEqual(web_user.get_user_data('ANOTHER_DOMAIN').to_dict(), {
            'commcare_project': 'ANOTHER_DOMAIN',
            'commcare_profile': '',
            'start': 'sometimes',  # whoops, domain 1 affects other domains!
        })

    def test_lazy_init_and_save(self):
        # mimic loading a user from the db
        user = CommCareUser.wrap({
            '_id': str(uuid.uuid4()),
            'domain': self.domain,
            'username': 'birdman',
            'password': '***',
            'user_data': {'favorite_color': 'purple'},
        })
        with self.assertRaises(SQLUserData.DoesNotExist):
            SQLUserData.objects.get(domain=self.domain, user_id=user.user_id)

        # Accessing data for the first time saves it to SQL
        self.assertEqual(user.get_user_data(self.domain)['favorite_color'], 'purple')
        sql_data = SQLUserData.objects.get(domain=self.domain, user_id=user.user_id)
        self.assertEqual(sql_data.data['favorite_color'], 'purple')

        # Making a modification works immediately, but isn't persisted until user save
        user.get_user_data(self.domain)['favorite_color'] = 'blue'
        self.assertEqual(user.get_user_data(self.domain)['favorite_color'], 'blue')
        sql_data.refresh_from_db()
        self.assertEqual(sql_data.data['favorite_color'], 'purple')  # unchanged
        user.save()
        self.addCleanup(user.delete, self.domain, deleted_by=None)
        sql_data.refresh_from_db()
        self.assertEqual(sql_data.data['favorite_color'], 'blue')


def _get_profile(self, profile_id):
    if profile_id == 'blues':
        return CustomDataFieldsProfile(
            id=profile_id,
            name='blues',
            fields={'favorite_color': 'blue'},
        )
    if profile_id == 'others':
        return CustomDataFieldsProfile(
            id=profile_id,
            name='others',
            fields={},
        )
    raise CustomDataFieldsProfile.DoesNotExist()


@patch('corehq.apps.users.user_data.UserData._get_profile', new=_get_profile)
class TestUserDataModel(SimpleTestCase):
    domain = 'test-user-data-model'

    def test_add_and_remove_profile(self):
        # Custom user data profiles get their data added to metadata automatically for mobile users
        user_data = UserData({'yearbook_quote': 'Not all who wander are lost.'}, self.domain)
        self.assertEqual(user_data.to_dict(), {
            'commcare_project': self.domain,
            'commcare_profile': '',
            'yearbook_quote': 'Not all who wander are lost.',
        })

        user_data.profile_id = 'blues'
        self.assertEqual(user_data.to_dict(), {
            'commcare_project': self.domain,
            'commcare_profile': 'blues',
            'favorite_color': 'blue',  # provided by the profile
            'yearbook_quote': 'Not all who wander are lost.',
        })

        # Remove profile should remove it and related fields
        user_data.profile_id = None
        self.assertEqual(user_data.to_dict(), {
            'commcare_project': self.domain,
            'commcare_profile': '',
            'yearbook_quote': 'Not all who wander are lost.',
        })

    def test_profile_conflicts_with_data(self):
        user_data = UserData({'favorite_color': 'purple'}, self.domain)
        with self.assertRaisesMessage(UserDataError, "Profile conflicts with existing data"):
            user_data.profile_id = 'blues'

    def test_profile_conflicts_with_blank_existing_data(self):
        user_data = UserData({'favorite_color': ''}, self.domain)
        user_data.profile_id = 'blues'
        self.assertEqual(user_data['favorite_color'], 'blue')

    def test_avoid_conflict_by_blanking_out(self):
        user_data = UserData({'favorite_color': 'purple'}, self.domain)
        user_data.update({
            'favorite_color': '',
        }, profile_id='blues')
        self.assertEqual(user_data['favorite_color'], 'blue')

    def test_data_conflicts_with_profile(self):
        user_data = UserData({}, self.domain, profile_id='blues')
        with self.assertRaisesMessage(UserDataError, "'favorite_color' cannot be set directly"):
            user_data['favorite_color'] = 'purple'

    def test_profile_and_data_conflict(self):
        user_data = UserData({}, self.domain)
        with self.assertRaisesMessage(UserDataError, "'favorite_color' cannot be set directly"):
            user_data.update({
                'favorite_color': 'purple',
            }, profile_id='blues')

    def test_update_shows_changed(self):
        user_data = UserData({}, self.domain)
        changed = user_data.update({'favorite_color': 'purple'})
        self.assertTrue(changed)
        changed = user_data.update({'favorite_color': 'purple'})
        self.assertFalse(changed)

    def test_update_order_irrelevant(self):
        user_data = UserData({}, self.domain, profile_id='blues')
        user_data.update({
            'favorite_color': 'purple',  # this is compatible with the new profile, but not the old
        }, profile_id='others')

    def test_ignore_noop_conflicts_with_profile(self):
        user_data = UserData({}, self.domain, profile_id='blues')
        # this key is in the profile, but the values are the same
        user_data['favorite_color'] = 'blue'

    def test_remove_profile(self):
        user_data = UserData({}, self.domain, profile_id='blues')
        user_data.profile_id = None
        self.assertEqual(user_data.profile_id, None)
        self.assertEqual(user_data.profile, None)

    def test_remove_profile_and_clear(self):
        user_data = UserData({}, self.domain, profile_id='blues')
        user_data.update({
            'favorite_color': '',
        }, profile_id=None)

    def test_delitem(self):
        user_data = UserData({'yearbook_quote': 'something random'}, self.domain)
        del user_data['yearbook_quote']
        self.assertNotIn('yearbook_quote', user_data.to_dict())

    def test_popitem(self):
        user_data = UserData({'yearbook_quote': 'something random'}, self.domain)
        res = user_data.pop('yearbook_quote')
        self.assertEqual(res, 'something random')
        self.assertNotIn('yearbook_quote', user_data.to_dict())

        self.assertEqual(user_data.pop('yearbook_quote', 'MISSING'), 'MISSING')
        with self.assertRaises(KeyError):
            user_data.pop('yearbook_quote')

    def test_remove_unrecognized(self):
        user_data = UserData({
            'in_schema': 'true',
            'not_in_schema': 'true',
            'commcare_location_id': '123',
        }, self.domain)
        changed = user_data.remove_unrecognized({'in_schema', 'in_schema_not_doc'})
        self.assertTrue(changed)
        self.assertEqual(user_data.raw, {'in_schema': 'true', 'commcare_location_id': '123'})

    def test_remove_unrecognized_empty_field(self):
        user_data = UserData({}, self.domain)
        changed = user_data.remove_unrecognized(set())
        self.assertFalse(changed)
        self.assertEqual(user_data.raw, {})
        changed = user_data.remove_unrecognized({'a', 'b'})
        self.assertFalse(changed)
        self.assertEqual(user_data.raw, {})
