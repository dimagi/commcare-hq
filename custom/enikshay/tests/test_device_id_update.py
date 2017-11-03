from __future__ import absolute_import
from django.test import TestCase, override_settings, Client


from corehq.apps.ota.tests.test_restore_user_check import _get_auth_header
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.domain.models import Domain

from corehq.util import reverse
from corehq.util.test_utils import flag_enabled
from custom.enikshay.tests.utils import ENikshayCaseStructureMixin


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
@flag_enabled('ENIKSHAY')
class DeviceIdUpdateTest(ENikshayCaseStructureMixin, TestCase):

    def setUp(self):
        super(DeviceIdUpdateTest, self).setUp()
        self.domain_obj = Domain(name=self.domain)
        self.domain_obj.save()
        self.web_user_username = "user@example.com"
        self.web_user_password = "123"
        self.web_user = WebUser.create(
            self.domain,
            username=self.web_user_username,
            password=self.web_user_password,
        )

    def tearDown(self):
        self.domain_obj.delete()
        super(DeviceIdUpdateTest, self).tearDown()

    def test_login_as(self):

        self.web_user.is_superuser = True
        self.web_user.save()

        restore_uri = reverse('ota_restore', args=[self.domain])
        auth_header = _get_auth_header(self.web_user_username, self.web_user_password)
        client = Client(HTTP_AUTHORIZATION=auth_header)
        device_id = "foo"

        resp = client.get(restore_uri, data={'as': self.username, "device_id": device_id}, follow=True)
        self.assertEqual(resp.status_code, 200)

        restored_as_user = CommCareUser.get_by_username(self.username)

        self.assertEqual(len(restored_as_user.devices), 1)
        self.assertEqual(restored_as_user.devices[0].device_id, device_id)
