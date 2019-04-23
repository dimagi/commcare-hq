from __future__ import absolute_import
from __future__ import unicode_literals

import base64

from django.test.client import Client
from django.urls import reverse

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser


class OdataTestMixin(object):

    view_urlname = None

    @classmethod
    def setUpClass(cls):
        super(OdataTestMixin, cls).setUpClass()
        cls.client = Client()
        cls.domain = Domain(name='test_domain')
        cls.domain.save()
        cls.web_user = WebUser.create(cls.domain.name, 'test_user', 'my_password')

    def tearDown(self):
        super(OdataTestMixin, self).tearDown()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.web_user.delete()
        super(OdataTestMixin, cls).tearDownClass()

    def test_no_credentials(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 401)

    def test_wrong_password(self):
        wrong_credentials = self._get_basic_credentials(self.web_user.username, 'wrong_password')
        response = self._execute_query(wrong_credentials)
        self.assertEqual(response.status_code, 401)

    def test_wrong_domain(self):
        other_domain = Domain(name='other_domain')
        other_domain.save()
        self.addCleanup(other_domain.delete)
        correct_credentials = self._get_correct_credentials()
        response = self.client.get(
            reverse(self.view_urlname, kwargs={'domain': other_domain.name}),
            HTTP_AUTHORIZATION='Basic ' + correct_credentials,
        )
        self.assertEqual(response.status_code, 403)

    def test_missing_feature_flag(self):
        correct_credentials = self._get_correct_credentials()
        response = self._execute_query(correct_credentials)
        self.assertEqual(response.status_code, 404)

    @property
    def view_url(self):
        return reverse(self.view_urlname, kwargs={'domain': self.domain.name})

    def _execute_query(self, credentials):
        return self.client.get(self.view_url, HTTP_AUTHORIZATION='Basic ' + credentials)

    @staticmethod
    def _get_correct_credentials():
        return OdataTestMixin._get_basic_credentials('test_user', 'my_password')

    @staticmethod
    def _get_basic_credentials(username, password):
        return base64.b64encode("{}:{}".format(username, password).encode('utf-8')).decode('utf-8')
