from django.core.urlresolvers import reverse
import django.test
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import normalize_username
from couchforms.models import XFormInstance
import django_digest.test
from django.utils.unittest.case import TestCase
import os
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.shortcuts import create_domain, create_user
from corehq.apps.receiverwrapper.views import secure_post


class AuthTest(TestCase):

    def setUp(self):
        self.domain = 'my-crazy-domain'
        create_domain(self.domain)

        try:
            self.user = CommCareUser.create(
                self.domain,
                username=normalize_username('danny', self.domain),
                password='1234',
            )
        except CommCareUser.Inconsistent:
            pass

        self.app = Application.new_app(self.domain, 'My Crazy App', '2.0')
        self.app.save()

        self.file_path = os.path.join(
            os.path.dirname(__file__), "data", 'bare_form.xml'
        )
        self.url = reverse(secure_post, args=[self.domain, self.app.get_id])

    def _test_post(self, client, url, expected_auth_context):
        with open(self.file_path, "rb") as f:
            response = client.post(url, {"xml_submission_file": f})
        xform_id = response['X-CommCareHQ-FormID']
        xform = XFormInstance.get(xform_id)
        self.assertEqual(xform.auth_context, expected_auth_context)
        return xform

    def test_digest(self):
        client = django_digest.test.Client()
        client.set_authorization(self.user.username, '1234',
                                 method='Digest')
        self._test_post(client, self.url, {
            'doc_type': 'AuthContext',
            'domain': self.domain,
            'authenticated': True,
            'user_id': self.user.get_id,
        })

    def test_noauth(self):
        client = django.test.Client()
        self._test_post(client, self.url + '?authtype=noauth', {
            'doc_type': 'AuthContext',
            'domain': self.domain,
            'authenticated': False,
            'user_id': None,
        })
