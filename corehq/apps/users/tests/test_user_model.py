from datetime import datetime
from django.test import TestCase, SimpleTestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser, DeviceIdLastUsed
from corehq.form_processor.utils import get_simple_wrapped_form, TestFormMetadata
from corehq.form_processor.tests.utils import run_with_all_backends, FormProcessorTestUtils


class UserModelTest(TestCase):

    def setUp(self):
        super(UserModelTest, self).setUp()
        self.domain = 'my-domain'
        self.domain_obj = create_domain(self.domain)
        self.user = CommCareUser.create(
            domain=self.domain,
            username='birdman',
            password='***',
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

    @run_with_all_backends
    def test_get_form_ids(self):
        form_ids = list(self.user._get_form_ids())
        self.assertEqual(len(form_ids), 1)
        self.assertEqual(form_ids[0], '123')


class CommCareUserWrapTest(SimpleTestCase):

    def test_wrap_device_ids(self):
        data = {
            'doc_type': 'CommCareUser',
            'username': 'larry',
            'first_name': 'Lawrence',
            'last_name': 'Laffer',
            'email': 'larry@sierra.com',
            'password': 'Ken sent me',
            'device_ids': ['35-209900-176148-1'],
            'created_on': '2016-07-24T06:43:46.440887Z',
            'status': 'site_edited',
            'language': 'en',
        }
        user = CommCareUser.wrap(data)
        self.assertEqual(user.device_ids, [
            DeviceIdLastUsed(
                device_id='35-209900-176148-1',
                doc_type='DeviceIdLastUsed',
                last_used=datetime(2016, 7, 24, 6, 43, 46, 440887))
        ])
