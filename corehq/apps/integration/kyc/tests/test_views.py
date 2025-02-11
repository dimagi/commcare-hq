from django.test import TestCase
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.integration.kyc.views import KycConfigurationView
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled


class TestKycConfigurationView(TestCase):
    domain = 'test-domain'
    urlname = KycConfigurationView.urlname

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.username = 'test-user'
        cls.password = '1234'
        cls.webuser = WebUser.create(
            cls.domain,
            cls.username,
            cls.password,
            None,
            None,
            is_admin=True,
        )
        cls.webuser.save()

    @classmethod
    def tearDownClass(cls):
        cls.webuser.delete(None, None)
        cls.domain_obj.delete()
        super().tearDownClass()

    @property
    def endpoint(self):
        return reverse(self.urlname, args=(self.domain,))

    @property
    def login_endpoint(self):
        return reverse('domain_login', kwargs={'domain': self.domain})

    def _make_request(self, is_logged_in=True):
        if is_logged_in:
            self.client.login(username=self.username, password=self.password)
        return self.client.get(self.endpoint)

    def test_not_logged_in(self):
        response = self._make_request(is_logged_in=False)
        self.assertRedirects(response, f'/accounts/login/?next={self.endpoint}')

    def test_ff_not_enabled(self):
        response = self._make_request()
        self.assertEqual(response.status_code, 404)

    @flag_enabled('KYC_VERIFICATION')
    def test_success(self):
        response = self._make_request()
        self.assertEqual(response.status_code, 200)
