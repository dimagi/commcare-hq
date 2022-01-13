from datetime import datetime, timedelta

from django.test import SimpleTestCase, TestCase

from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
    PROFILE_SLUG,
)
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser, DeviceAppMeta, WebUser
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

        self.metadata = TestFormMetadata(
            domain=self.user.domain,
            user_id=self.user._id,
        )
        get_simple_wrapped_form('123', metadata=self.metadata)

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

    def test_user_data_not_allowed_in_create(self):
        message = "Do not access user_data directly, pass metadata argument to create."
        with self.assertRaisesMessage(ValueError, message):
            CommCareUser.create(self.domain, 'martha', 'bmfa', None, None, user_data={'country': 'Canada'})

    def test_metadata(self):
        metadata = self.user.metadata
        self.assertEqual(metadata, {'commcare_project': 'my-domain'})
        metadata.update({
            'cruise': 'control',
            'this': 'road',
        })
        self.user.update_metadata(metadata)
        self.assertEqual(self.user.metadata, {
            'commcare_project': 'my-domain',
            'cruise': 'control',
            'this': 'road',
        })
        self.user.pop_metadata('cruise')
        self.assertEqual(self.user.metadata, {
            'commcare_project': 'my-domain',
            'this': 'road',
        })
        self.user.update_metadata({'this': 'field'})
        self.assertEqual(self.user.metadata, {
            'commcare_project': 'my-domain',
            'this': 'field',
        })

    def test_metadata_with_profile(self):
        definition = CustomDataFieldsDefinition(domain='my-domain', field_type=UserFieldsView.field_type)
        definition.save()
        definition.set_fields([Field(slug='start')])
        definition.save()
        profile = CustomDataFieldsProfile(
            name='low',
            fields={'start': 'sometimes'},
            definition=definition,
        )
        profile.save()
        conflict_message = "metadata properties conflict with profile: start"

        # Custom user data profiles get their data added to metadata automatically for mobile users
        self.user.update_metadata({PROFILE_SLUG: profile.id})
        self.assertEqual(self.user.metadata, {
            'commcare_project': 'my-domain',
            PROFILE_SLUG: profile.id,
            'start': 'sometimes',
        })

        # Remove profile should remove it and related fields
        self.user.pop_metadata(PROFILE_SLUG)
        self.assertEqual(self.user.metadata, {
            'commcare_project': 'my-domain',
        })

        # Can't add profile that conflicts with existing data
        self.user.update_metadata({
            'start': 'never',
            'end': 'yesterday',
        })
        with self.assertRaisesMessage(ValueError, conflict_message):
            self.user.update_metadata({
                PROFILE_SLUG: profile.id,
            })

        # Can't add data that conflicts with existing profile
        self.user.pop_metadata('start')
        self.user.update_metadata({PROFILE_SLUG: profile.id})
        with self.assertRaisesMessage(ValueError, conflict_message):
            self.user.update_metadata({'start': 'never'})

        # Can't add both a profile and conflicting data
        self.user.pop_metadata(PROFILE_SLUG)
        with self.assertRaisesMessage(ValueError, conflict_message):
            self.user.update_metadata({
                PROFILE_SLUG: profile.id,
                'start': 'never',
            })

        # Custom user data profiles don't get populated for web users
        web_user = WebUser.create(None, "imogen", "*****", None, None)
        self.assertEqual(web_user.metadata, {
            'commcare_project': None,
        })
        web_user.update_metadata({PROFILE_SLUG: profile.id})
        self.assertEqual(web_user.metadata, {
            'commcare_project': None,
            PROFILE_SLUG: profile.id,
        })

        definition.delete()
        web_user.delete(self.domain, deleted_by=None)

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

    def test_merge_device_app_meta(self):
        m1 = DeviceAppMeta(
            build_id='build1',
            build_version=1,
            last_submission=datetime.utcnow(),
            num_unsent_forms=1
        )
        m2 = DeviceAppMeta(
            build_id='build2',
            build_version=2,
            last_submission=datetime.utcnow(),
        )

        m2.merge(m1)
        self.assertNotEqual(m2.build_id, m1.build_id)
        self.assertNotEqual(m2.build_version, m1.build_version)
        self.assertNotEqual(m2.last_submission, m1.last_submission)
        self.assertIsNone(m2.num_unsent_forms)

        m1.merge(m2)
        self.assertEqual(m1.build_id, m2.build_id)
        self.assertEqual(m1.build_version, m2.build_version)
        self.assertEqual(m1.last_submission, m2.last_submission)
        self.assertEqual(m1.num_unsent_forms, 1)

    def test_merge_device_app_meta_last_is_none(self):
        m1 = DeviceAppMeta(
            last_submission=datetime.utcnow(),
        )
        m2 = DeviceAppMeta(
            last_sync=datetime.utcnow(),
        )

        m1.merge(m2)
        self.assertEqual(m1.last_sync, m2.last_sync)
