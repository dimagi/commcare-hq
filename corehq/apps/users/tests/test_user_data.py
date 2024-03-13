import uuid
from unittest.mock import patch, PropertyMock

from django.test import SimpleTestCase, TestCase

from corehq.apps.custom_data_fields.models import CustomDataFieldsProfile, Field, CustomDataFieldsDefinition
from corehq.apps.users.views.mobile.custom_data_fields import CUSTOM_USER_DATA_FIELD_TYPE
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.management.commands.populate_sql_user_data import (
    get_users_without_user_data,
    populate_user_data,
)
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.user_data import (
    SQLUserData,
    UserData,
    UserDataError,
    prime_user_data_caches,
)


class TestUserData(TestCase):
    domain = 'test-user-data'

    @classmethod
    def setUpTestData(cls):
        delete_all_users()

    def make_commcare_user(self):
        user = CommCareUser.create(self.domain, str(uuid.uuid4()), '***', None, None, timezone="UTC")
        self.addCleanup(user.delete, self.domain, deleted_by=None)
        return user

    def make_web_user(self):
        user = WebUser.create(self.domain, str(uuid.uuid4()), '***', None, None, timezone="UTC")
        self.addCleanup(user.delete, self.domain, deleted_by=None)
        return user

    def test_user_data_accessor(self):
        user = self.make_commcare_user()
        user_data = user.get_user_data(self.domain)
        self.assertEqual(user_data['commcare_project'], self.domain)
        user_data.update({
            'cruise': 'control',
            'this': 'road',
        })

        # This will be persisted on user save
        with self.assertRaises(SQLUserData.DoesNotExist):
            SQLUserData.objects.get(user_id=user.user_id, domain=self.domain)
        user.save()
        sql_user_data = SQLUserData.objects.get(user_id=user.user_id, domain=self.domain)
        self.assertEqual(sql_user_data.data['this'], 'road')

    def test_web_users(self):
        web_user = self.make_web_user()
        user_data1 = web_user.get_user_data(self.domain)
        user_data1['what_domain_is_it'] = 'domain 1'

        user_data2 = web_user.get_user_data('another_domain')
        user_data2['what_domain_is_it'] = 'domain 2'

        # Each domain has a separate user_data object
        self.assertEqual(web_user.get_user_data(self.domain).to_dict(), {
            'commcare_project': self.domain,
            'commcare_profile': '',
            'what_domain_is_it': 'domain 1',
        })
        self.assertEqual(web_user.get_user_data('another_domain').to_dict(), {
            'commcare_project': 'another_domain',
            'commcare_profile': '',
            'what_domain_is_it': 'domain 2',
        })

    def test_migrate_get_users_without_user_data(self):
        users_without_data = [
            self.make_commcare_user(),
            self.make_commcare_user(),
            self.make_web_user(),
            self.make_web_user(),
        ]
        users_with_data = [self.make_commcare_user(), self.make_web_user()]
        for user in users_with_data:
            ud = user.get_user_data(self.domain)
            ud['key'] = 'dummy val so this is non-empty'
            ud.save()

        users_to_migrate = get_users_without_user_data()
        self.assertItemsEqual(
            [u.username for u in users_without_data],
            [u.username for u in users_to_migrate],
        )

    def test_migrate_commcare_user(self):
        user = self.make_commcare_user()
        user['user_data'] = {'favorite_color': 'purple'}
        user.save()
        populate_user_data(CommCareUser.get_db().get(user._id), user.get_django_user())
        sql_data = SQLUserData.objects.get(domain=self.domain, user_id=user.user_id)
        self.assertEqual(sql_data.data['favorite_color'], 'purple')

    def test_migrate_web_user(self):
        user = self.make_web_user()
        # one user data dictionary, gets copied to all domains
        user['user_data'] = {'favorite_color': 'purple'}
        user.add_domain_membership('domain2', timezone='UTC')
        user.save()
        populate_user_data(WebUser.get_db().get(user._id), user.get_django_user())
        for domain in [self.domain, 'domain2']:
            sql_data = SQLUserData.objects.get(domain=domain, user_id=user.user_id)
            self.assertEqual(sql_data.data['favorite_color'], 'purple')

    def test_migrate_user_no_data(self):
        user = self.make_commcare_user()
        populate_user_data(CommCareUser.get_db().get(user._id), user.get_django_user())
        with self.assertRaises(SQLUserData.DoesNotExist):
            SQLUserData.objects.get(domain=self.domain, user_id=user.user_id)

    def test_prime_user_data_caches(self):
        users = [
            self.make_commcare_user(),
            self.make_commcare_user(),
            self.make_commcare_user(),
            self.make_web_user(),
            self.make_web_user(),
        ]
        for user in users:
            ud = user.get_user_data(self.domain)
            ud['key'] = 'dummy val so this is non-empty'
            ud.save()
        users.append(self.make_web_user())  # add user without data
        self.assertEqual(SQLUserData.objects.count(), 5)

        for user in users:
            user._user_data_accessors = {}  # wipe cache
        with patch('corehq.apps.users.user_data.UserData.for_user') as init_method:
            users = prime_user_data_caches(users, self.domain)
            for user in users:
                user.get_user_data(self.domain)
            self.assertEqual(init_method.call_count, 0)

    def test_prime_user_data_caches_avoids_multiple_schema_lookups(self):
        users = [
            self.make_commcare_user()
        ]

        fields_definition = CustomDataFieldsDefinition.objects.create(
            domain=self.domain, field_type=CUSTOM_USER_DATA_FIELD_TYPE)
        fields_definition.set_fields([Field(slug='field1', label='Field1')])

        users = list(prime_user_data_caches(users, self.domain))

        fields_definition.set_fields([Field(slug='updated', label='Updated')])
        user_data = users[0].get_user_data(self.domain).to_dict()
        self.assertIn('field1', user_data)


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

    def setUp(self):
        self.user_fields = []
        field_patcher = patch('corehq.apps.users.user_data.UserData._schema_fields', new_callable=PropertyMock)
        mocked_schema_fields = field_patcher.start()
        mocked_schema_fields.side_effect = lambda: self.user_fields

        self.addCleanup(field_patcher.stop)

    def init_user_data(self, raw_user_data=None, profile_id=None):
        return UserData(
            raw_user_data=raw_user_data or {},
            couch_user=None,  # This is only used for saving to the db
            domain=self.domain,
            profile_id=profile_id,
        )

    def test_defaults_unspecified_schema_properties_to_empty(self):
        self.user_fields = [Field(slug='one')]
        user_data = self.init_user_data({})
        result = user_data.to_dict()
        self.assertEqual(result['one'], '')

    def test_specified_user_data_overrides_schema_defaults(self):
        self.user_fields = [Field(slug='one')]
        user_data = self.init_user_data({'one': 'some_value'})
        result = user_data.to_dict()
        self.assertEqual(result['one'], 'some_value')

    def test_add_and_remove_profile(self):
        # Custom user data profiles get their data added to metadata automatically for mobile users
        user_data = self.init_user_data({'yearbook_quote': 'Not all who wander are lost.'})
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
        user_data = self.init_user_data({'favorite_color': 'purple'})
        with self.assertRaisesMessage(UserDataError, "Profile conflicts with existing data"):
            user_data.profile_id = 'blues'

    def test_profile_conflicts_with_blank_existing_data(self):
        user_data = self.init_user_data({'favorite_color': ''})
        user_data.profile_id = 'blues'
        self.assertEqual(user_data['favorite_color'], 'blue')

    def test_avoid_conflict_by_blanking_out(self):
        user_data = self.init_user_data({'favorite_color': 'purple'})
        user_data.update({
            'favorite_color': '',
        }, profile_id='blues')
        self.assertEqual(user_data['favorite_color'], 'blue')

    def test_data_conflicts_with_profile(self):
        user_data = self.init_user_data({}, profile_id='blues')
        with self.assertRaisesMessage(UserDataError, "'favorite_color' cannot be set directly"):
            user_data['favorite_color'] = 'purple'

    def test_profile_and_data_conflict(self):
        user_data = self.init_user_data({})
        with self.assertRaisesMessage(UserDataError, "'favorite_color' cannot be set directly"):
            user_data.update({
                'favorite_color': 'purple',
            }, profile_id='blues')

    def test_update_shows_changed(self):
        user_data = self.init_user_data({})
        changed = user_data.update({'favorite_color': 'purple'})
        self.assertTrue(changed)
        changed = user_data.update({'favorite_color': 'purple'})
        self.assertFalse(changed)

    def test_update_order_irrelevant(self):
        user_data = self.init_user_data({}, profile_id='blues')
        user_data.update({
            'favorite_color': 'purple',  # this is compatible with the new profile, but not the old
        }, profile_id='others')

    def test_ignore_noop_conflicts_with_profile(self):
        user_data = self.init_user_data({}, profile_id='blues')
        # this key is in the profile, but the values are the same
        user_data['favorite_color'] = 'blue'

    def test_remove_profile(self):
        user_data = self.init_user_data({}, profile_id='blues')
        user_data.profile_id = None
        self.assertEqual(user_data.profile_id, None)
        self.assertEqual(user_data.profile, None)

    def test_remove_profile_and_clear(self):
        user_data = self.init_user_data({}, profile_id='blues')
        user_data.update({
            'favorite_color': '',
        }, profile_id=None)

    def test_delitem(self):
        user_data = self.init_user_data({'yearbook_quote': 'something random'})
        del user_data['yearbook_quote']
        self.assertNotIn('yearbook_quote', user_data.to_dict())

    def test_popitem(self):
        user_data = self.init_user_data({'yearbook_quote': 'something random'})
        res = user_data.pop('yearbook_quote')
        self.assertEqual(res, 'something random')
        self.assertNotIn('yearbook_quote', user_data.to_dict())

        self.assertEqual(user_data.pop('yearbook_quote', 'MISSING'), 'MISSING')
        with self.assertRaises(KeyError):
            user_data.pop('yearbook_quote')

    def test_remove_unrecognized(self):
        user_data = self.init_user_data({
            'in_schema': 'true',
            'not_in_schema': 'true',
            'commcare_location_id': '123',
        })
        changed = user_data.remove_unrecognized({'in_schema', 'in_schema_not_doc'})
        self.assertTrue(changed)
        self.assertEqual(user_data.raw, {'in_schema': 'true', 'commcare_location_id': '123'})

    def test_remove_unrecognized_empty_field(self):
        user_data = self.init_user_data({})
        changed = user_data.remove_unrecognized(set())
        self.assertFalse(changed)
        self.assertEqual(user_data.raw, {})
        changed = user_data.remove_unrecognized({'a', 'b'})
        self.assertFalse(changed)
        self.assertEqual(user_data.raw, {})
