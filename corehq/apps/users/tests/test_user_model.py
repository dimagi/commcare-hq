from datetime import datetime, timedelta

from django.test import SimpleTestCase, TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import (
    CommCareUser,
    CouchUser,
    DeviceAppMeta,
    WebUser,
)
from corehq.apps.users.models_role import UserRole
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.form_processor.utils import (
    TestFormMetadata,
    get_simple_wrapped_form,
)
from corehq.util.test_utils import softer_assert


class UserModelTest(TestCase):

    def setUp(self):
        super(UserModelTest, self).setUp()
        self.domain = 'my-domain'
        self.domain_obj = create_domain(self.domain)
        self.user = CommCareUser.create(
            domain=self.domain,
            username='birdman',
            password='***',
            created_by=None,
            created_via=None,
        )

        metadata = TestFormMetadata(
            domain=self.user.domain,
            user_id=self.user._id,
        )
        get_simple_wrapped_form('123', metadata=metadata)

    def tearDown(self):
        CommCareUser.get_db().delete_doc(self.user._id)
        FormProcessorTestUtils.delete_all_xforms(self.domain)
        self.domain_obj.delete()
        super(UserModelTest, self).tearDown()

    def create_user(self, username, is_web_user=True):
        UserClass = WebUser if is_web_user else CommCareUser
        return UserClass.create(
            domain=self.domain,
            username=username,
            password='***',
            created_by=None,
            created_via=None,
        )

    def test_get_form_ids(self):
        form_ids = list(self.user._get_form_ids())
        self.assertEqual(len(form_ids), 1)
        self.assertEqual(form_ids[0], '123')

    def test_last_modified(self):
        lm = self.user.last_modified
        self.user.save()
        user = CommCareUser.get(self.user._id)
        self.assertGreater(user.last_modified, lm)

    @softer_assert()
    def test_last_modified_bulk(self):
        lm = self.user.last_modified
        CommCareUser.save_docs([self.user])
        user = CommCareUser.get(self.user._id)
        self.assertGreater(user.last_modified, lm)

        lm = self.user.last_modified
        CommCareUser.bulk_save([self.user])
        user = CommCareUser.get(self.user._id)
        self.assertGreater(user.last_modified, lm)

    def test_commcare_user_lockout_limits(self):
        commcare_user = self.create_user('test_user', is_web_user=False)

        with self.subTest('User is locked out'):
            commcare_user.login_attempts = 500
            self.assertTrue(commcare_user.is_locked_out())

        with self.subTest('User is not locked out'):
            commcare_user.login_attempts = 499
            self.assertFalse(commcare_user.is_locked_out())

    def test_web_user_lockout_limits(self):
        web_user = self.create_user('test_user', is_web_user=True)

        with self.subTest('User is locked out'):
            web_user.login_attempts = 5
            self.assertTrue(web_user.is_locked_out())

        with self.subTest('User is not locked out'):
            web_user.login_attempts = 4
            self.assertFalse(web_user.is_locked_out())

    def test_commcare_user_with_no_lockouts_is_not_locked_out(self):
        commcare_user = self.create_user('test_user', is_web_user=False)

        self.domain_obj.disable_mobile_login_lockout = True
        self.domain_obj.save()

        commcare_user.login_attempts = 100
        self.assertFalse(commcare_user.is_locked_out())


class UserDeviceTest(SimpleTestCase):

    def test_add_single_device(self):
        user = CommCareUser()
        now = datetime.utcnow()
        device_id = 'my-new-cool-phone'
        self.assertEqual([], user.devices)
        user.update_device_id_last_used(device_id, now)
        self.assertEqual(1, len(user.devices))
        device = user.devices[0]
        self.assertEqual(device_id, device.device_id)
        self.assertEqual(now, device.last_used)

    def test_add_second_device(self):
        user = CommCareUser()
        now = datetime.utcnow()
        later = now + timedelta(seconds=1)
        first_device = 'first-device'
        second_device = 'second-device'
        user.update_device_id_last_used(first_device, now)
        user.update_device_id_last_used(second_device, later)
        self.assertEqual(2, len(user.devices))
        device_date_mapping = {device.device_id: device.last_used for device in user.devices}
        self.assertEqual({first_device, second_device}, set(device_date_mapping.keys()))
        self.assertEqual(now, device_date_mapping[first_device])
        self.assertEqual(later, device_date_mapping[second_device])

    def test_update_existing_devices(self):
        user = CommCareUser()
        now = datetime.utcnow()
        later = now + timedelta(days=1, seconds=1)
        way_later = now + timedelta(days=1, seconds=2)
        first_device = 'first-device'
        second_device = 'second-device'
        user.update_device_id_last_used(first_device, now)
        user.update_device_id_last_used(second_device, now)
        user.update_device_id_last_used(first_device, later)
        user.update_device_id_last_used(second_device, way_later)
        self.assertEqual(2, len(user.devices))
        device_date_mapping = {device.device_id: device.last_used for device in user.devices}
        self.assertEqual({first_device, second_device}, set(device_date_mapping.keys()))
        self.assertEqual(later, device_date_mapping[first_device])
        self.assertEqual(way_later, device_date_mapping[second_device])

    def test_only_update_once_per_day(self):
        user = CommCareUser()
        when = datetime(2000, 1, 1)
        later = when + timedelta(hours=1)
        day_later = when + timedelta(days=1)
        device = 'device'
        self.assertTrue(user.update_device_id_last_used(device, when))
        self.assertFalse(user.update_device_id_last_used(device, later))
        self.assertTrue(user.update_device_id_last_used(device, day_later))

    def test_update_app_metadata(self):
        user = CommCareUser()
        app_meta = DeviceAppMeta(
            app_id='123',
            build_id='build1',
            build_version=1,
            last_submission=datetime.utcnow(),
            num_unsent_forms=1
        )
        user.update_device_id_last_used('device', device_app_meta=app_meta)
        device = user.get_device('device')
        app_meta = device.get_meta_for_app('123')
        self.assertIsNotNone(app_meta)


class TestCommCareUserRoles(TestCase):
    user_class = CommCareUser

    @classmethod
    def setUpClass(cls):
        super(TestCommCareUserRoles, cls).setUpClass()
        cls.domain = 'test-user-role'
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.get_db().delete_doc, cls.domain_obj)

        cls.role1 = UserRole.create(domain=cls.domain, name="role1")
        cls.role2 = UserRole.create(domain=cls.domain, name="role2")
        cls.mobile_worker_default_role = UserRole.commcare_user_default(cls.domain)

    def test_create_user_without_role(self):
        user = self._create_user('scotch game')

        # expect that a CommCareUser without a role will get the default role
        self.check_role(user, self.mobile_worker_default_role)

    def test_create_user_with_role(self):
        user = self._create_user('vienna game', role_id=self.role1.get_id)
        self.check_role(user, self.role1)

    def test_set_role(self):
        user = self._create_user("bird's opening")

        user.set_role(self.domain, self.role1.get_qualified_id())
        user.save()

        # check that the role is applied to the current user object
        self.check_role(user, self.role1)

        # check that a fresh object from the DB is correct
        user = CouchUser.get_by_username(user.username)
        self.check_role(user, self.role1)

    def test_update_role(self):
        user = self._create_user("alekhine's defense", role_id=self.role1.get_id)

        user.set_role(self.domain, self.role2.get_qualified_id())
        user.save()

        # check that the role is applied to the current user object
        self.check_role(user, self.role2)

        # check that a fresh object from the DB is correct
        user = CouchUser.get_by_username(user.username)
        self.check_role(user, self.role2)

    def test_role_deleted(self):
        role = UserRole.create(self.domain, 'new')
        user = self._create_user("king's gambit", role_id=role.get_id)
        self.check_role(user, role)

        role.delete()

        user = CouchUser.get_by_username(user.username)
        self.assertIsNone(user.get_role(self.domain))

    def check_role(self, user, expected, domain=None):
        role = user.get_role(domain or self.domain)
        self.assertIsNotNone(role)
        self.assertEqual(role.get_qualified_id(), expected.get_qualified_id())

    def _create_user(self, username, role_id=None):
        user = self.user_class.create(
            domain=self.domain,
            username=username,
            password='***',
            created_by=None,
            created_via=None,
            role_id=role_id
        )
        self.addCleanup(user.delete, None, None)
        return user


class TestWebUserRoles(TestCommCareUserRoles):
    user_class = WebUser

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain2 = 'test-user-role2'
        cls.domain_obj2 = create_domain(cls.domain2)
        cls.addClassCleanup(cls.domain_obj2.get_db().delete_doc, cls.domain_obj2)

    def test_create_user_without_role(self):
        user = self._create_user('scotch game')

        # web users don't have default roles
        self.assertIsNone(user.get_role(self.domain))

    def test_roles_multiple_domains(self):
        user = self._create_user("alekhine's defense")
        user.add_as_web_user(self.domain, self.role1.get_qualified_id())
        user.add_as_web_user(self.domain2, self.role2.get_qualified_id())

        self.check_role(user, self.role1, self.domain)
        self.check_role(user, self.role2, self.domain2)
