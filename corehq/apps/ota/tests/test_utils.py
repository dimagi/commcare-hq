import uuid
from datetime import datetime
from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from freezegun import freeze_time

from casexml.apps.phone.models import OTARestoreCommCareUser, OTARestoreWebUser, SyncLogSQL
from corehq.apps.domain.models import Domain
from corehq.apps.locations.tests.util import LocationHierarchyTestCase
from corehq.apps.ota.utils import get_restore_user, is_permitted_to_restore, can_login_on_device
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.util import format_username


class RestorePermissionsTest(LocationHierarchyTestCase):
    domain = 'goats'
    other_domain = 'sheep'
    location_type_names = ['country', 'state']
    location_structure = [
        ('usa', [
            ('ma', []),
        ]),
        ('canada', [
            ('montreal', []),
        ]),
    ]

    @classmethod
    def setUpClass(cls):
        super(RestorePermissionsTest, cls).setUpClass()

        cls.other_project = Domain(name=cls.other_domain)
        cls.other_project.save()

        cls.web_user = WebUser.create(
            username='billy@goats.com',
            domain=cls.domain,
            password='***',
            created_by=None,
            created_via=None,
        )
        cls.super_user = WebUser.create(
            username='super@woman.com',
            domain=cls.other_domain,
            password='***',
            created_by=None,
            created_via=None,
        )
        cls.super_user.is_superuser = True
        cls.super_user.save()
        cls.commcare_user = CommCareUser.create(
            username=format_username('super', cls.domain),
            domain=cls.domain,
            password='***',
            created_by=None,
            created_via=None,
        )
        cls.no_edit_commcare_user = CommCareUser.create(
            username=format_username('noedit', cls.domain),
            domain=cls.domain,
            password='***',
            created_by=None,
            created_via=None,
        )
        cls.location_user = CommCareUser.create(
            username=format_username('location', cls.domain),
            domain=cls.domain,
            password='***',
            created_by=None,
            created_via=None,
        )
        cls.wrong_location_user = CommCareUser.create(
            username=format_username('wrong-location', cls.domain),
            domain=cls.domain,
            password='***',
            created_by=None,
            created_via=None,
        )
        cls.web_location_user = WebUser.create(
            username='web-location@location.com',
            domain=cls.domain,
            password='***',
            created_by=None,
            created_via=None,
        )

        cls.commcare_user.set_location(cls.locations['usa'])
        cls.web_location_user.set_location(cls.domain, cls.locations['usa'])
        cls.no_edit_commcare_user.set_location(cls.locations['usa'])
        cls.location_user.set_location(cls.locations['ma'])
        cls.wrong_location_user.set_location(cls.locations['montreal'])

        cls.restrict_user_to_assigned_locations(cls.commcare_user)
        cls.restrict_user_to_assigned_locations(cls.web_location_user)

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        cls.other_project.delete()
        super(RestorePermissionsTest, cls).tearDownClass()

    def test_commcare_user_permitted(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.commcare_user,
            None,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

    def test_commcare_user_wrong_domain(self):
        is_permitted, message = is_permitted_to_restore(
            'wrong-domain',
            self.commcare_user,
            None,
        )
        self.assertFalse(is_permitted)
        self.assertRegex(message, 'was not in the domain')

    def test_web_user_permitted(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_user,
            None,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

    def test_web_user_as_user_permitted(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_user,
            self.commcare_user,
        )
        self.assertTrue(is_permitted)

    def test_web_user_as_other_web_user(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_user,
            self.web_user,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

    def test_commcare_user_as_self(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.commcare_user,
            self.commcare_user,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

    def test_web_user_as_self(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_user,
            self.web_user,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

    def test_super_user_as_user_other_domain(self):
        """
        Superusers should be able to restore as other mobile users even if it's the wrong domain
        """
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.super_user,
            self.commcare_user,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

    def test_commcare_user_as_user_disallow_no_edit_data(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.no_edit_commcare_user,
            self.location_user,
        )
        self.assertFalse(is_permitted)
        self.assertRegex(message, 'does not have permission')

    def test_commcare_user_as_user_in_location(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.commcare_user,
            self.location_user,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.commcare_user,
            self.wrong_location_user,
        )
        self.assertFalse(is_permitted)
        self.assertRegex(message, 'not in allowed locations')

    def test_web_user_as_user_in_location(self):
        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_location_user,
            self.location_user,
        )
        self.assertTrue(is_permitted)
        self.assertIsNone(message)

        is_permitted, message = is_permitted_to_restore(
            self.domain,
            self.web_location_user,
            self.wrong_location_user,
        )
        self.assertFalse(is_permitted)
        self.assertRegex(message, 'not in allowed locations')


class RestorePermissionsTestLimitLoginAs(TestCase):
    domain = 'goats_do_roam'

    @classmethod
    def setUpClass(cls):
        super(RestorePermissionsTestLimitLoginAs, cls).setUpClass()

        cls.project = Domain(name=cls.domain)
        cls.project.save()

        cls.restore_user = WebUser.create(
            username=format_username('malbec', cls.domain),
            domain=cls.domain,
            password='***',
            created_by=None,
            created_via=None,
        )
        cls.commcare_user = CommCareUser.create(
            username=format_username('shiraz', cls.domain),
            domain=cls.domain,
            password='***',
            created_by=None,
            created_via=None,
        )
        cls.commcare_user_login_as = CommCareUser.create(
            username=format_username('merlot', cls.domain),
            domain=cls.domain,
            password='***',
            created_by=None,
            created_via=None,
            user_data={"login_as_user": cls.restore_user.username},
        )
        cls.commcare_user_login_as_multiple_upper_case = CommCareUser.create(
            username=format_username('cabernet', cls.domain),
            domain=cls.domain,
            password='***',
            created_by=None,
            created_via=None,
            user_data={
                "login_as_user": f"{format_username('ruby', cls.domain)} {cls.restore_user.username.upper()}"
            },
        )
        cls.commcare_user_default_login_as = CommCareUser.create(
            username=format_username('pinotage', cls.domain),
            domain=cls.domain,
            password='***',
            created_by=None,
            created_via=None,
            user_data={
                "login_as_user": "someone@else deFAUlt"  # intentionally mixed case to test case sensitivity
            },
        )

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        Domain.get_db().delete_doc(cls.project)
        super(RestorePermissionsTestLimitLoginAs, cls).tearDownClass()

    def test_user_limited_login_as_denied(self):
        with patch("corehq.apps.ota.utils._limit_login_as", return_value=True):
            is_permitted, message = is_permitted_to_restore(
                self.domain,
                self.restore_user,
                self.commcare_user,
            )
            self.assertFalse(is_permitted)
            self.assertRegex(message, "not available as login-as user")

    def test_user_limited_login_as_permitted(self):
        with patch("corehq.apps.ota.utils._limit_login_as", return_value=True):
            is_permitted, message = is_permitted_to_restore(
                self.domain,
                self.restore_user,
                self.commcare_user_login_as,
            )
            self.assertIsNone(message)
            self.assertTrue(is_permitted)

    def test_user_limited_login_as_permitted_case_insensitive_match_multiple_users(self):
        with patch("corehq.apps.ota.utils._limit_login_as", return_value=True):
            is_permitted, message = is_permitted_to_restore(
                self.domain,
                self.restore_user,
                self.commcare_user_login_as_multiple_upper_case,
            )
            self.assertIsNone(message)
            self.assertTrue(is_permitted)

    def test_user_limited_login_as_default_denied(self):
        with patch("corehq.apps.ota.utils._limit_login_as", return_value=True):
            is_permitted, message = is_permitted_to_restore(
                self.domain,
                self.restore_user,
                self.commcare_user_default_login_as,
            )
            self.assertFalse(is_permitted)
            self.assertRegex(message, "not available as login-as user")

    def test_user_limited_login_as_default_permitted(self):
        with patch("corehq.apps.ota.utils._limit_login_as", return_value=True), \
             patch("corehq.apps.ota.utils._can_access_default_login_as_user", return_value=True):
            is_permitted, message = is_permitted_to_restore(
                self.domain,
                self.restore_user,
                self.commcare_user_default_login_as,
            )
            self.assertIsNone(message)
            self.assertTrue(is_permitted)


class GetRestoreUserTest(TestCase):

    domain = 'goats'
    other_domain = 'sheep'

    @classmethod
    def setUpClass(cls):
        super(GetRestoreUserTest, cls).setUpClass()
        cls.project = Domain(name=cls.domain)
        cls.project.save()

        cls.other_project = Domain(name=cls.other_domain)
        cls.other_project.save()

        cls.web_user = WebUser.create(
            username='billy@goats.com',
            domain=cls.domain,
            password='***',
            created_by=None,
            created_via=None,
        )
        cls.commcare_user = CommCareUser.create(
            username=format_username('jane', cls.domain),
            domain=cls.domain,
            password='***',
            created_by=None,
            created_via=None,
        )
        cls.other_commcare_user = CommCareUser.create(
            username=format_username('john', cls.domain),
            domain=cls.domain,
            password='***',
            created_by=None,
            created_via=None,
        )
        cls.super_user = WebUser.create(
            username='super@woman.com',
            domain=cls.other_domain,
            password='***',
            created_by=None,
            created_via=None,
        )
        cls.super_user.is_superuser = True
        cls.super_user.save()

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        cls.project.delete()
        cls.other_project.delete()
        super(GetRestoreUserTest, cls).tearDownClass()

    def test_get_restore_user_web_user(self):
        self.assertIsInstance(get_restore_user(self.domain, self.web_user, None), OTARestoreWebUser)

    def test_get_restore_user_commcare_user(self):
        user = get_restore_user(self.domain, self.commcare_user, None)
        self.assertIsInstance(user, OTARestoreCommCareUser)
        self.assertEqual(user.request_user_id, self.commcare_user.user_id)

    def test_get_restore_user_as_user(self):
        self.assertIsInstance(
            get_restore_user(
                self.domain,
                self.web_user,
                self.commcare_user
            ),
            OTARestoreCommCareUser,
        )

    def test_get_restore_user_as_web_user(self):
        self.assertIsInstance(
            get_restore_user(
                self.domain,
                self.web_user,
                self.web_user
            ),
            OTARestoreWebUser,
        )

    def test_get_restore_user_as_super_user(self):
        self.assertIsInstance(
            get_restore_user(
                self.domain,
                self.web_user,
                self.super_user
            ),
            OTARestoreWebUser,
        )

    def test_get_restore_user_as_user_for_commcare_user(self):
        user = get_restore_user(
            self.domain,
            self.commcare_user,
            self.other_commcare_user
        )
        self.assertEqual(user.user_id, self.other_commcare_user._id)
        self.assertEqual(user.request_user_id, self.commcare_user.user_id)


@freeze_time("2024-12-10 12:00:00")
class CanLoginOnDeviceTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'devices-per-user-test'
        cls.within_past_day = datetime(2024, 12, 10, 0, 0)
        cls.over_one_day_ago = datetime(2024, 12, 9, 0, 0)

    @override_settings(DEVICES_PER_USER=1)
    def test_allowed_if_device_count_equals_limit_but_existing_device_id(self):
        self._create_synclog(self.domain, 'abc123', 'device-id', date=self.within_past_day)

        self.assertTrue(can_login_on_device('abc123', 'device-id'))

    @override_settings(DEVICES_PER_USER=1)
    def test_not_allowed_if_device_count_equals_limit_and_new_device_id(self):
        self._create_synclog(self.domain, 'abc123', 'device-id', date=self.within_past_day)

        self.assertFalse(can_login_on_device('abc123', 'new-device-id'))

    @override_settings(DEVICES_PER_USER=2)
    def test_allowed_if_device_count_is_under_limit(self):
        self._create_synclog(self.domain, 'abc123', 'device-id', date=self.within_past_day)

        self.assertTrue(can_login_on_device('abc123', 'new-device-id'))

    @override_settings(DEVICES_PER_USER=1)
    def test_web_apps_logins_are_always_allowed(self):
        for i in range(3):
            self._create_synclog(self.domain, 'abc123', f'WebAppsLogin*{i}', date=self.within_past_day)

        self.assertTrue(can_login_on_device('abc123', 'WebAppsLogin*newlogin'))

    @override_settings(DEVICES_PER_USER=2)
    def test_web_apps_logins_do_not_count_towards_device_count(self):
        for i in range(3):
            self._create_synclog(self.domain, 'abc123', f'WebAppsLogin*{i}', date=self.within_past_day)

        self._create_synclog(self.domain, 'abc123', 'device-id', date=self.within_past_day)

        self.assertTrue(can_login_on_device('abc123', 'new-device-id'))

    @override_settings(DEVICES_PER_USER=1)
    def test_activity_older_than_a_day_is_ignored(self):
        for i in range(2):
            self._create_synclog(self.domain, 'abc123', f'device-{i}', date=self.over_one_day_ago)

        self.assertTrue(can_login_on_device('abc123', 'new-device-id'))

    @override_settings(DEVICES_PER_USER=2)
    def test_either_date_or_last_submitted_counts_towards_device_count(self):
        self._create_synclog(
            self.domain,
            'abc123',
            'device-1',
            date=self.over_one_day_ago,
            last_submitted=self.within_past_day,
        )

        self._create_synclog(
            self.domain,
            'abc123',
            'device-2',
            date=self.within_past_day,
            last_submitted=self.over_one_day_ago,
        )

        self.assertFalse(can_login_on_device('abc123', 'new-device-id'))

    def test_allowed_if_empty_queryset(self):
        self.assertTrue(can_login_on_device('abc123', 'device-0'))

    @override_settings(DEVICES_PER_USER=1)
    def test_allowed_for_different_user(self):
        self._create_synclog(self.domain, 'abc123', 'device-id', date=self.within_past_day)

        self.assertTrue(can_login_on_device('def456', 'device-id'))

    @override_settings(DEVICES_PER_USER=1)
    def test_device_id_is_none_is_allowed(self):
        self._create_synclog(self.domain, 'abc123', 'device-id', date=self.within_past_day)

        self.assertTrue(can_login_on_device('abc123', 'device-id'))

    def _create_synclog(self, domain, user_id, device_id, **kwargs):
        SyncLogSQL.objects.create(
            domain=domain,
            doc={},
            synclog_id=uuid.uuid4(),
            user_id=user_id,
            device_id=device_id,
            **kwargs
        )
