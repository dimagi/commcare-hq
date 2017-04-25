from datetime import datetime, timedelta
from django.test import TestCase, SimpleTestCase
from django.contrib.auth.models import User

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.utils import get_simple_wrapped_form, TestFormMetadata
from corehq.form_processor.tests.utils import run_with_all_backends, FormProcessorTestUtils


class UserModelTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(UserModelTest, cls).setUpClass()
        cls.domain = 'my-domain'
        cls.domain_obj = create_domain(cls.domain)
        cls.user = CommCareUser.create(
            domain=cls.domain,
            username='birdman',
            password='***',
        )

        cls.metadata = TestFormMetadata(
            domain=cls.user.domain,
            user_id=cls.user._id,
        )
        get_simple_wrapped_form('123', metadata=cls.metadata)

    @classmethod
    def tearDownClass(cls):
        CommCareUser.get_db().delete_doc(cls.user._id)
        FormProcessorTestUtils.delete_all_xforms(cls.domain)
        cls.domain_obj.delete()
        super(UserModelTest, cls).tearDownClass()

    @run_with_all_backends
    def test_get_form_ids(self):
        form_ids = list(self.user._get_form_ids())
        self.assertEqual(len(form_ids), 1)
        self.assertEqual(form_ids[0], '123')

    def test_django_user_commcare_fields(self):
        django_user = User.objects.get(djangousercommcarefields__couch_user_id=self.user._id)
        self.assertIsNotNone(django_user)


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
        self.assertEqual(set([first_device, second_device]), set(device_date_mapping.keys()))
        self.assertEqual(now, device_date_mapping[first_device])
        self.assertEqual(later, device_date_mapping[second_device])

    def test_update_existing_devices(self):
        user = CommCareUser()
        now = datetime.utcnow()
        later = now + timedelta(seconds=1)
        way_later = now + timedelta(seconds=2)
        first_device = 'first-device'
        second_device = 'second-device'
        user.update_device_id_last_used(first_device, now)
        user.update_device_id_last_used(second_device, now)
        user.update_device_id_last_used(first_device, later)
        user.update_device_id_last_used(second_device, way_later)
        self.assertEqual(2, len(user.devices))
        device_date_mapping = {device.device_id: device.last_used for device in user.devices}
        self.assertEqual(set([first_device, second_device]), set(device_date_mapping.keys()))
        self.assertEqual(later, device_date_mapping[first_device])
        self.assertEqual(way_later, device_date_mapping[second_device])
