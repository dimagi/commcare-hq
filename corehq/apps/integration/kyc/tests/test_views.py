from unittest.mock import patch

from django.test import RequestFactory, TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseFactory

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.integration.kyc.models import KycConfig, UserDataStore
from corehq.apps.integration.kyc.views import (
    KycConfigurationView,
    KycVerificationReportView,
    KycVerificationTableView,
)
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.util.test_utils import flag_enabled


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
        assert response.status_code == 404

    def test_ff_not_enabled(self):
        response = self._make_request()
        assert response.status_code == 404

    @flag_enabled('KYC_VERIFICATION')
    @patch('corehq.apps.integration.kyc.forms.get_case_types_for_domain', return_value=['case-1'])
    def test_success(self, *args):
        response = self._make_request()
        assert response.status_code == 200


class TestKycVerificationReportView(BaseTestKycView):
    urlname = KycVerificationReportView.urlname

    def test_not_logged_in(self):
        response = self._make_request(is_logged_in=False)
        assert response.status_code == 404

    def test_ff_not_enabled(self):
        response = self._make_request()
        assert response.status_code == 404

    @flag_enabled('KYC_VERIFICATION')
    def test_success(self):
        response = self._make_request()
        assert response.status_code == 200

    @flag_enabled('KYC_VERIFICATION')
    def test_domain_has_config_context(self):
        response = self._make_request()
        assert response.context['domain_has_config'] is False

        kyc_config = KycConfig.objects.create(
            domain=self.domain,
            user_data_store=UserDataStore.CUSTOM_USER_DATA,
            api_field_to_user_data_map=[],
        )
        self.addCleanup(kyc_config.delete)
        response = self._make_request()
        assert response.context['domain_has_config'] is True

    def test_domain_has_config_false(self):
        view = KycVerificationReportView()
        view.args = (self.domain,)
        view.request = RequestFactory().get(self.endpoint)

        context = view.page_context
        assert 'domain_has_config' in context
        assert context['domain_has_config'] is False

    def test_domain_has_config_true(self):
        kyc_config = KycConfig.objects.create(
            domain=self.domain,
            user_data_store=UserDataStore.CUSTOM_USER_DATA,
            api_field_to_user_data_map=[],
        )
        self.addCleanup(kyc_config.delete)

        view = KycVerificationReportView()
        view.args = (self.domain,)
        view.request = RequestFactory().get(self.endpoint)

        context = view.page_context
        assert 'domain_has_config' in context
        assert context['domain_has_config'] is True


@es_test(requires=[case_search_adapter], setup_class=True)
class TestKycVerificationTableView(BaseTestKycView):
    urlname = KycVerificationTableView.urlname

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kyc_mapping = {
            # API field: User data
            'first_name': 'name',
            'last_name': 'last_name',
            'email': 'email',
            'phone_number': 'phone_number',
            'national_id_number': 'national_id_number',
            'street_address': 'street_address',
            'city': 'city',
            'post_code': 'post_code',
            'country': 'country',
        }
        cls.kyc_config = KycConfig.objects.create(
            domain=cls.domain,
            user_data_store=UserDataStore.CUSTOM_USER_DATA,
            api_field_to_user_data_map=cls.kyc_mapping,
        )
        cls.addClassCleanup(cls.kyc_config.delete)
        cls.user1 = CommCareUser.create(
            cls.domain,
            'user1',
            'password',
            created_by=None,
            created_via=None,
            first_name='John',
            last_name='Doe',
            email='jdoe@example.org',
            user_data={
                'name': 'Johnny',
                'phone_number': '1234567890',
                'national_id_number': '1234567890',
                'street_address': '123 Main St',
                'city': 'Anytown',
                'post_code': '12345',
                'country': 'Anyplace',
            }
        )
        cls.user2 = CommCareUser.create(
            cls.domain,
            'user2',
            'password',
            created_by=None,
            created_via=None,
            first_name='Jane',
            last_name='Doe',
        )

        factory = CaseFactory(cls.domain)
        cls.case_list = [
            _create_case(
                factory,
                name='foo',
                data={
                    'first_name': 'Bob',
                    'last_name': 'Smith',
                    'home_email': 'bsmith@example.org',
                    'phone_number': '0987654321',
                    'national_id_number': '0987654321',
                    'street_address': '456 Main St',
                    'city': 'Sometown',
                    'post_code': '54321',
                    'country': 'Someplace',
                }),
            _create_case(
                factory,
                name='bar',
                data={
                    'first_name': 'Foo',
                    'last_name': 'Bar'
                }),
        ]
        case_search_adapter.bulk_index(cls.case_list, refresh=True)

    @classmethod
    def tearDownClass(cls):
        cls.user1.delete(None, None)
        cls.user2.delete(None, None)
        super().tearDownClass()

    def test_not_logged_in(self):
        response = self._make_request(is_logged_in=False)
        self.assertRedirects(response, f'/accounts/login/?next={self.endpoint}')

    def test_ff_not_enabled(self):
        response = self._make_request()
        assert response.status_code == 404

    @flag_enabled('KYC_VERIFICATION')
    def test_success(self):
        response = self._make_request()
        assert response.status_code == 200

    @flag_enabled('KYC_VERIFICATION')
    def test_response_data_users(self):
        response = self._make_request()
        queryset = response.context['table'].data
        assert len(queryset) == 2
        for row in queryset:
            if row['has_invalid_data']:
                assert row == {
                    'id': self.user2.user_id,
                    'has_invalid_data': True,
                    'kyc_verification_status': None,
                    'kyc_last_verified_at': None,
                    'name': 'Jane Doe',
                    'last_name': 'Doe',
                    'kyc_verification_error': None,
                }
            else:
                assert row == {
                    'id': self.user1.user_id,
                    'has_invalid_data': False,
                    'kyc_verification_status': None,
                    'kyc_last_verified_at': None,
                    'name': 'Johnny',
                    'last_name': 'Doe',
                    'email': 'jdoe@example.org',
                    'phone_number': '1234567890',
                    'national_id_number': '1234567890',
                    'street_address': '123 Main St',
                    'city': 'Anytown',
                    'post_code': '12345',
                    'country': 'Anyplace',
                    'kyc_verification_error': None,
                }

    @flag_enabled('KYC_VERIFICATION')
    def test_response_data_cases(self):
        self.kyc_config.user_data_store = UserDataStore.OTHER_CASE_TYPE
        self.kyc_config.other_case_type = 'other-case'
        self.kyc_config.api_field_to_user_data_map.update({
            'first_name': 'first_name',
            'last_name': 'last_name',
            'email': 'home_email',
        })
        self.kyc_config.save()

        response = self._make_request()
        queryset = response.context['table'].data
        assert len(queryset) == 2
        for row in queryset:
            if row['has_invalid_data']:
                assert row == {
                    'id': self.case_list[1].case_id,
                    'has_invalid_data': True,
                    'kyc_verification_status': None,
                    'kyc_last_verified_at': None,
                    'first_name': 'Foo',
                    'last_name': 'Bar',
                    'kyc_verification_error': None,
                }
            else:
                assert row == {
                    'id': self.case_list[0].case_id,
                    'has_invalid_data': False,
                    'kyc_verification_status': None,
                    'kyc_last_verified_at': None,
                    'first_name': 'Bob',
                    'last_name': 'Smith',
                    'home_email': 'bsmith@example.org',
                    'phone_number': '0987654321',
                    'national_id_number': '0987654321',
                    'street_address': '456 Main St',
                    'city': 'Sometown',
                    'post_code': '54321',
                    'country': 'Someplace',
                    'kyc_verification_error': None,
                }


def _create_case(factory, name, data):
    return factory.create_case(
        case_name=name,
        case_type='other-case',
        update=data
    )
