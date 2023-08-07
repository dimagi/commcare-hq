from unittest.mock import patch

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test.testcases import SimpleTestCase
from django.utils.safestring import SafeData

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.users.models import CommCareUser, UserHistory
from corehq.apps.users.util import (
    SYSTEM_USER_ID,
    bulk_auto_deactivate_commcare_users,
    cached_user_id_to_user_display,
    generate_mobile_username,
    get_complete_mobile_username,
    is_username_available,
    user_display_string,
    user_id_to_username,
    username_to_user_id,
)
from corehq.apps.users.views.utils import (
    _get_locations_with_orphaned_cases,
    get_user_location_info,
)
from corehq.const import USER_CHANGE_VIA_AUTO_DEACTIVATE


class TestUsernameToUserID(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestUsernameToUserID, cls).setUpClass()
        cls.domain = 'scale-domain'
        cls.user = CommCareUser.create(cls.domain, 'scale', 'dude', None, None)
        cache.clear()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain, deleted_by=None)
        cache.clear()
        super(TestUsernameToUserID, cls).tearDownClass()

    def test_username_to_user_id(self):
        user_id = username_to_user_id(self.user.username)
        self.assertEqual(user_id, self.user._id)

    def test_username_to_user_id_wrong_username(self):
        user_id = username_to_user_id('not-here')
        self.assertIsNone(user_id)


class TestUserIdToUsernameToUserName(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestUserIdToUsernameToUserName, cls).setUpClass()
        cls.domain = 'test-domain'
        cls.user_without_name = CommCareUser.create(cls.domain, 'no_name', 'a_secret', None, None)
        cls.user_with_first_name = CommCareUser.create(cls.domain, 'first_name', 'a_secret', None, None,
                                                       first_name='Alice')
        cls.user_with_last_name = CommCareUser.create(cls.domain, 'last_name', 'a_secret', None, None,
                                                      last_name='Jones')
        cls.user_with_full_name = CommCareUser.create(cls.domain, 'full_name', 'a_secret', None, None,
                                                      first_name='Alice', last_name='Jones')
        cls.users = [
            cls.user_without_name,
            cls.user_with_first_name,
            cls.user_with_last_name,
            cls.user_with_full_name,
        ]
        cache.clear()

    @classmethod
    def tearDownClass(cls):
        for user in cls.users:
            user.delete(cls.domain, deleted_by=None)
        cache.clear()
        super(TestUserIdToUsernameToUserName, cls).tearDownClass()

    def test_user_id_to_username_no_names(self):
        for user in self.users:
            self.assertEqual(user.username, user_id_to_username(user.user_id))

    def test_user_id_to_username_with_names(self):
        self.assertEqual('no_name', user_id_to_username(self.user_without_name.user_id,
                                                        use_name_if_available=True))
        self.assertEqual('Alice', user_id_to_username(self.user_with_first_name.user_id,
                                                      use_name_if_available=True))
        self.assertEqual('Jones', user_id_to_username(self.user_with_last_name.user_id,
                                                      use_name_if_available=True))
        self.assertEqual('Alice Jones', user_id_to_username(self.user_with_full_name.user_id,
                                                            use_name_if_available=True))

    def test_cached_user_id_to_user_display(self):
        self.assertEqual('Alice', cached_user_id_to_user_display(self.user_with_first_name.user_id))
        self.assertEqual('Alice Jones', cached_user_id_to_user_display(self.user_with_full_name.user_id))
        self.user_with_first_name.first_name = 'Betty'
        self.user_with_first_name.save()
        self.assertEqual('Betty', user_id_to_username(self.user_with_first_name.user_id,
                                                      use_name_if_available=True))
        self.assertEqual('Alice', cached_user_id_to_user_display(self.user_with_first_name.user_id))
        self.assertEqual('Alice Jones', cached_user_id_to_user_display(self.user_with_full_name.user_id))
        # set username back because other tests rely on it
        self.user_with_first_name.first_name = 'Alice'
        self.user_with_first_name.save()


class TestUserDisplayString(SimpleTestCase):
    def test_all_names(self):
        result = user_display_string('test@dimagi.com', 'Test', 'User')
        self.assertEqual(result, 'test@dimagi.com "Test User"')

    def test_only_username(self):
        result = user_display_string('test@dimagi.com', '', '')
        self.assertEqual(result, 'test@dimagi.com')

    def test_is_escaped(self):
        result = user_display_string('test@d<i>magi.com', 'T<e>st', 'U<s>er')
        self.assertEqual(result, 'test@d&lt;i&gt;magi.com "T&lt;e&gt;st U&lt;s&gt;er"')

    def test_is_safe(self):
        result = user_display_string('<b>@dimagi.com', '', '')
        self.assertIsInstance(result, SafeData)

    # NOTE: Documenting existing functionality. This function may not need to handle None
    def test_handles_none_names(self):
        result = user_display_string('test@dimagi.com', None, None)
        self.assertEqual(result, 'test@dimagi.com')


class TestBulkAutoDeactivateCommCareUser(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain = 'test-domain'
        cls.active_user = CommCareUser.create(
            cls.domain,
            'active',
            'secret',
            None,
            None,
            is_active=True,
        )
        cls.inactive_user = CommCareUser.create(
            cls.domain,
            'inactive',
            'secret',
            None,
            None,
            is_active=False,
        )

        cache.clear()

    def tearDown(self):
        UserHistory.objects.all().delete()
        super().tearDown()

    @classmethod
    def tearDownClass(cls):
        cls.active_user.delete(cls.domain, deleted_by=None)
        cls.inactive_user.delete(cls.domain, deleted_by=None)
        cache.clear()
        super().tearDownClass()

    def test_user_is_deactivated_and_logged(self):
        bulk_auto_deactivate_commcare_users([self.active_user.get_id], self.domain)
        refreshed_user = CommCareUser.get_by_user_id(self.active_user.user_id)
        self.assertFalse(
            refreshed_user.is_active
        )
        user_history = UserHistory.objects.get(user_id=self.active_user.user_id)
        self.assertEqual(
            user_history.by_domain,
            self.domain
        )
        self.assertEqual(
            user_history.for_domain,
            self.domain
        )
        self.assertEqual(
            user_history.changed_by,
            SYSTEM_USER_ID
        )
        self.assertEqual(
            user_history.changed_via,
            USER_CHANGE_VIA_AUTO_DEACTIVATE
        )

    def test_user_is_not_deactivated_and_no_logs(self):
        bulk_auto_deactivate_commcare_users([self.inactive_user.user_id], self.domain)
        refreshed_user = CommCareUser.get_by_user_id(self.inactive_user.get_id)
        self.assertFalse(
            refreshed_user.is_active
        )
        self.assertFalse(
            UserHistory.objects.filter(user_id=self.inactive_user.user_id).exists()
        )


class TestGenerateMobileUsername(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain('test-domain')
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.user = CommCareUser.create(cls.domain, 'test-user@test-domain.commcarehq.org', 'abc123', None, None)
        cls.addClassCleanup(cls.user.delete, cls.domain, None)

    def test_successfully_generated_username(self):
        try:
            username = generate_mobile_username('test-user-1', self.domain)
        except ValidationError:
            self.fail(f'Unexpected raised exception: {ValidationError}')

        self.assertEqual(username, 'test-user-1@test-domain.commcarehq.org')

    def test_exception_raised_if_username_validation_fails(self):
        with self.assertRaises(ValidationError):
            generate_mobile_username('test%user', self.domain)


class TestIsUsernameAvailable(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain('test-domain')
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.user = CommCareUser.create(cls.domain, 'test-user@test-domain.commcarehq.org', 'abc123', None,
                                       None)
        cls.addClassCleanup(cls.user.delete, cls.domain, None)

    def test_returns_true_if_available(self):
        self.assertTrue(is_username_available('unused-test-user@test-domain.commcarehq.org'))

    def test_returns_false_if_actively_in_use(self):
        self.assertFalse(is_username_available('test-user@test-domain.commcarehq.org'))

    def test_returns_false_if_previously_used(self):
        retired_user = CommCareUser.create(self.domain, 'retired@test-domain.commcarehq.org', 'abc123', None,
                                           None)
        self.addCleanup(retired_user.delete, self.domain, None)
        retired_user.retire(self.domain, None)

        self.assertFalse(is_username_available('retired@test-domain.commcarehq.org'))

    def test_returns_false_if_reserved_username(self):
        self.assertFalse(is_username_available('admin'))
        self.assertFalse(is_username_available('demo_user@test-domain.commcarehq.org'))


class TestGetCompleteMobileUsername(SimpleTestCase):

    def test_returns_unchanged_username_if_already_complete(self):
        username = get_complete_mobile_username('test@test-domain.commcarehq.org', 'test-domain')
        self.assertEqual(username, 'test@test-domain.commcarehq.org')

    def test_returns_complete_username_if_incomplete(self):
        username = get_complete_mobile_username('test', 'test-domain')
        self.assertEqual(username, 'test@test-domain.commcarehq.org')


class TestGetLocationsWithOrphanedCases(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)
        cls.user_id = 'test-user-id'
        cls.location_ids = ['123', '456']

        cls.country = LocationType.objects.create(
            domain=cls.domain,
            name='country',
            view_descendants=True
        )
        cls.province = LocationType.objects.create(
            domain=cls.domain,
            name='province'
        )
        cls.orphan_location = SQLLocation.objects.create(
            domain=cls.domain,
            name='Brazil',
            location_id='123',
            location_type=cls.country
        )
        cls.shared_location = SQLLocation.objects.create(
            domain=cls.domain,
            name='Asia',
            location_id='456',
            location_type=cls.country
        )
        cls.descendant_location = SQLLocation.objects.create(
            domain=cls.domain,
            name='Rio',
            location_id='789',
            location_type=cls.province,
            parent=cls.orphan_location
        )

    @classmethod
    def tearDownClass(cls):
        cls.orphan_location.delete()
        cls.shared_location.delete()
        cls.descendant_location.delete()
        cls.domain_obj.delete()

        super().tearDownClass()

    @patch(
        'corehq.apps.users.views.utils._get_location_ids_with_other_users',
        return_value={'123', '456'}
    )
    def test_no_locations(self, _):
        locations = _get_locations_with_orphaned_cases(self.domain, self.location_ids, self.user_id)
        self.assertEqual(len(locations), 0)

    @patch(
        'corehq.apps.users.views.utils._get_location_ids_with_other_users',
        return_value={'456'}
    )
    @patch(
        'corehq.apps.users.views.utils._get_location_case_counts',
        return_value={'123': 1, '789': 3}
    )
    def test_with_locations(self, _, __):
        locations = _get_locations_with_orphaned_cases(self.domain, self.location_ids, self.user_id)
        self.assertEqual(locations, {'Brazil': 1, 'Brazil/Rio': 3})

    @patch(
        'corehq.apps.users.views.utils._get_location_ids_with_other_users',
        return_value={'456'}
    )
    @patch(
        'corehq.apps.users.views.utils._get_location_case_counts',
        return_value={'123': 1, '789': 3}
    )
    def test_get_user_location_info(self, _, __):
        location_info = get_user_location_info(self.domain, self.location_ids, self.user_id)
        self.assertEqual(location_info['orphaned_case_count_per_location'], {'Brazil': 1, 'Brazil/Rio': 3})
        self.assertEqual(location_info['shared_locations'], {'456'})
