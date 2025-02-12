from django.test import TestCase
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.integration.kyc.views import (
    KycConfigurationView,
    KycVerificationReportView,
    KycVerificationTableView,
)
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled

from corehq.apps.integration.kyc.models import KycConfig, UserDataStore
from corehq.motech.models import ConnectionSettings
from corehq.apps.users.models import CommCareUser


class BaseTestKycView(TestCase):
    domain = 'test-domain'

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


class TestKycConfigurationView(BaseTestKycView):
    urlname = KycConfigurationView.urlname

    def test_not_logged_in(self):
        response = self._make_request(is_logged_in=False)
        self.assertEqual(response.status_code, 404)

    def test_ff_not_enabled(self):
        response = self._make_request()
        self.assertEqual(response.status_code, 404)

    @flag_enabled('KYC_VERIFICATION')
    def test_success(self):
        response = self._make_request()
        self.assertEqual(response.status_code, 200)


class TestKycVerificationReportView(BaseTestKycView):
    urlname = KycVerificationReportView.urlname

    def test_not_logged_in(self):
        response = self._make_request(is_logged_in=False)
        self.assertEqual(response.status_code, 404)

    def test_ff_not_enabled(self):
        response = self._make_request()
        self.assertEqual(response.status_code, 404)

    @flag_enabled('KYC_VERIFICATION')
    def test_success(self):
        response = self._make_request()
        self.assertEqual(response.status_code, 200)


class TestKycVerificationTableView(BaseTestKycView):
    urlname = KycVerificationTableView.urlname

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        conn_settings = ConnectionSettings.objects.create(
            name='test-conn',
            url='http://test.com',
            username='test',
            password='test',
        )
        cls.addClassCleanup(conn_settings.delete)

        cls.kyc_config = KycConfig.objects.create(
            domain=cls.domain,
            user_data_store=UserDataStore.CUSTOM_USER_DATA,
            api_field_to_user_data_map=[],
            connection_settings=conn_settings,
        )
        cls.addClassCleanup(cls.kyc_config.delete)

        cls.user1 = CommCareUser.create(
            cls.domain,
            'user1',
            'password',
            created_by=None,
            created_via=None,
        )
        cls.user1.save()

    @classmethod
    def tearDownClass(cls):
        cls.user1.delete(None, None)
        super().tearDownClass()

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

    @flag_enabled('KYC_VERIFICATION')
    def test_invalid_data(self):
        response = self._make_request()
        queryset = response.context['table'].data
        self.assertEqual(len(queryset), 1)
        self.assertEqual(queryset[0], {
            'id': self.user1.user_id,
            'has_invalid_data': True
        })