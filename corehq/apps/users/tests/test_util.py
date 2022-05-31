from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test.testcases import SimpleTestCase
from django.utils.safestring import SafeData

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser, UserHistory
from corehq.apps.users.util import (
    SYSTEM_USER_ID,
    bulk_auto_deactivate_commcare_users,
    cached_user_id_to_user_display,
    generate_mobile_username,
    user_display_string,
    user_id_to_username,
    username_to_user_id,
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

    def setUp(self) -> None:
        super().setUp()
        self.user = CommCareUser.create(self.domain, 'test-user@test-domain.commcarehq.org', 'abc123', None, None)
        self.addCleanup(self.user.delete, self.domain, None)

    def test_successfully_generated_username(self):
        try:
            username = generate_mobile_username('test-user-1', self.domain)
        except ValidationError:
            self.fail(f'Unexpected raised exception: {ValidationError}')

        self.assertEqual(username, 'test-user-1@test-domain.commcarehq.org')

    def test_invalid_username_double_period_message(self):
        try:
            generate_mobile_username('test..user', self.domain)
        except ValidationError as e:
            self.assertEqual(e.message, 'Username may not contain consecutive . (period).')
        else:
            self.fail(f'Expected raised exception: {ValidationError}')

    def test_invalid_username_trailing_period_message(self):
        try:
            generate_mobile_username('test.user.', self.domain)
        except ValidationError as e:
            self.assertEqual(e.message, 'Username may not end with a . (period).')
        else:
            self.fail(f'Expected raised exception: {ValidationError}')

    def test_invalid_username_generic_message(self):
        try:
            generate_mobile_username('test%user', self.domain)
        except ValidationError as e:
            self.assertEqual(e.message, 'Username may not contain special characters.')
        else:
            self.fail(f'Expected raised exception: {ValidationError}')

    def test_username_actively_in_use_message(self):
        try:
            generate_mobile_username('test-user', self.domain)
        except ValidationError as e:
            self.assertEqual(e.message, "Username 'test-user' is already taken.")
        else:
            self.fail(f'Expected raised exception: {ValidationError}')

    def test_username_was_previously_in_use_message(self):
        self.user.retire(self.domain, None)
        try:
            generate_mobile_username('test-user', self.domain)
        except ValidationError as e:
            self.assertEqual(e.message, "Username 'test-user' belonged to a user that was deleted and "
                                        "cannot be reused.")
        else:
            self.fail(f'Expected raised exception: {ValidationError}')

    def test_username_is_reserved_message(self):
        try:
            generate_mobile_username('admin', self.domain)
        except ValidationError as e:
            self.assertEqual(e.message, "Username 'admin' is reserved.")
        else:
            self.fail(f'Expected raised exception: {ValidationError}')

    def test_invalid_domain_message(self):
        try:
            generate_mobile_username('test-user-1', None)
        except ValidationError as e:
            self.assertEqual(e.message, "Domain is required.")
        else:
            self.fail(f'Expected raised exception: {ValidationError}')
