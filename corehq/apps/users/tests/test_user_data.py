from datetime import datetime
import uuid
from unittest.mock import patch, PropertyMock

from django.test import TestCase
from corehq.apps.commtrack.tests.util import make_loc

from corehq.apps.custom_data_fields.models import CustomDataFieldsProfile, Field, CustomDataFieldsDefinition
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.views.mobile.custom_data_fields import CUSTOM_USER_DATA_FIELD_TYPE
from corehq.apps.users.dbaccessors import delete_all_users
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
            'commcare_profile': '',
            'what_domain_is_it': 'domain 1',
        })
        self.assertEqual(web_user.get_user_data('another_domain').to_dict(), {
            'commcare_profile': '',
            'what_domain_is_it': 'domain 2',
        })

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

    def test_profile(self):
        fields_definition = CustomDataFieldsDefinition.objects.create(
            domain=self.domain, field_type=CUSTOM_USER_DATA_FIELD_TYPE)
        profile = CustomDataFieldsProfile.objects.create(
            name='blues', fields={'favorite_color': 'blue'}, definition=fields_definition)

        user = self.make_commcare_user()
        user_data = user.get_user_data(self.domain)
        user_data.profile_id = profile.pk
        user_data.save()
        self.assertEqual(user_data.profile.pk, profile.pk)

        user_data.profile_id = None
        user_data.save()
        self.assertEqual(user_data.profile, None)


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
class TestUserDataModel(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestUserDataModel, cls).setUpClass()
        cls.domain = 'test-user-data-model'
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.loc1 = make_loc('1', 'loc1', cls.domain)
        cls.loc2 = make_loc('2', 'loc2', cls.domain)
        cls.loc_ids = [loc.location_id for loc in [cls.loc1, cls.loc2]]

    def setUp(self):
        self.user_fields = []
        field_patcher = patch('corehq.apps.users.user_data.UserData._schema_fields', new_callable=PropertyMock)
        mocked_schema_fields = field_patcher.start()
        mocked_schema_fields.side_effect = lambda: self.user_fields

        self.addCleanup(field_patcher.stop)

        self.user = CommCareUser.create(
            domain=self.domain,
            username='cc1',
            password='***',
            created_by=None,
            created_via=None,
            last_login=datetime.now()
        )
        self.addCleanup(self.user.delete, self.domain, deleted_by=None)

    def init_user_data(self, raw_user_data=None, profile_id=None, domain=None):
        return UserData(
            raw_user_data=raw_user_data or {},
            couch_user=self.user,
            domain=domain or self.domain,
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
            'commcare_profile': '',
            'yearbook_quote': 'Not all who wander are lost.',
        })

        user_data.profile_id = 'blues'
        self.assertEqual(user_data.to_dict(), {
            'commcare_profile': 'blues',
            'favorite_color': 'blue',  # provided by the profile
            'yearbook_quote': 'Not all who wander are lost.',
        })

        # Remove profile should remove it and related fields
        user_data.profile_id = None
        self.assertEqual(user_data.to_dict(), {
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
        self.assertEqual(user_data.profile, None)

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

    def test_no_location_info_in_user_data_when_no_location_assigned(self):
        user_data = self.user.get_user_data(self.domain)

        self.assertEqual(user_data.to_dict(), {
            'commcare_profile': '',
        })


class TestUserDataLifecycle(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain('user-data-lifecycle-test')
        cls.addClassCleanup(cls.domain.delete)

    def _create_user_data(self, user, domain, raw_user_data, commit=True):
        user_data = UserData(
            raw_user_data=raw_user_data,
            couch_user=user,
            domain=domain,
        )
        if commit:
            user_data.save()

    def _create_web_user(self, username):
        user = WebUser.create(self.domain.name, username, 'testpwd', None, None)
        self.addCleanup(user.delete, self.domain.name, deleted_by=None)
        return user

    def test_user_data_is_soft_deleted_when_domain_membership_is_deleted(self):
        web_user = self._create_web_user('test@example.com')
        self._create_user_data(web_user, self.domain.name, {'favorite_color': 'purple'})
        # test that removing this user's domain membership removes the user data
        self.assertTrue(
            SQLUserData.objects.filter(django_user=web_user.get_django_user(), domain=self.domain.name).exists()
        )
        web_user.delete_domain_membership(self.domain.name)
        self.assertFalse(
            SQLUserData.objects.filter(django_user=web_user.get_django_user(), domain=self.domain.name).exists()
        )
        self.assertTrue(
            SQLUserData.all_objects.filter(
                django_user=web_user.get_django_user(), domain=self.domain.name, deleted_on__isnull=False
            ).exists()
        )

    def test_user_data_is_undeleted_when_domain_membership_is_restored(self):
        web_user = self._create_web_user('test@example.com')
        self._create_user_data(web_user, self.domain.name, {'favorite_color': 'purple'})
        self.assertTrue(
            SQLUserData.objects.filter(django_user=web_user.get_django_user(), domain=self.domain.name).exists()
        )
        record = web_user.delete_domain_membership(self.domain.name, create_record=True)
        record.undo()
        self.assertTrue(
            SQLUserData.objects.filter(django_user=web_user.get_django_user(), domain=self.domain.name).exists()
        )
        self.assertFalse(
            SQLUserData.all_objects.filter(
                django_user=web_user.get_django_user(), domain=self.domain.name, deleted_on__isnull=False
            ).exists()
        )

    def test_user_data_for_another_domain_is_not_deleted(self):
        web_user = self._create_web_user('test@example.com')
        new_domain_obj = create_domain('new-domain')
        self.addCleanup(new_domain_obj.delete)
        web_user.add_domain_membership('new-domain')
        web_user.save()
        self._create_user_data(web_user, self.domain.name, {'favorite_color': 'purple'})
        self._create_user_data(web_user, 'new-domain', {'favorite_color': 'green'})

        self.assertTrue(
            SQLUserData.objects.filter(django_user=web_user.get_django_user(), domain='new-domain').exists()
        )
        web_user.delete_domain_membership(self.domain.name)
        self.assertTrue(
            SQLUserData.objects.filter(django_user=web_user.get_django_user(), domain='new-domain').exists()
        )
