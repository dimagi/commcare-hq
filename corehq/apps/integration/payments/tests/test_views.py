from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseFactory
from corehq.apps.case_importer.const import MOMO_PAYMENT_CASE_TYPE

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.integration.payments.const import PaymentProperties
from corehq.apps.integration.payments.models import MoMoConfig
from corehq.apps.integration.payments.views import (
    PaymentsVerificationReportView,
    PaymentsVerificationTableView,
    PaymentConfigurationView,
)
from corehq.apps.users.models import WebUser
from corehq.motech.models import ConnectionSettings
from corehq.util.test_utils import flag_enabled
from corehq.apps.integration.payments.filters import BatchNumberFilter


class BaseTestPaymentsView(TestCase):
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

    def _make_request(self, log_in=True, querystring=None):
        if log_in:
            self.client.login(username=self.username, password=self.password)

        url = self.endpoint
        if querystring:
            url += f'?{querystring}'

        return self.client.get(url)


class TestPaymentsVerificationReportView(BaseTestPaymentsView):
    urlname = PaymentsVerificationReportView.urlname

    def test_not_logged_in(self):
        response = self._make_request(log_in=False)
        assert response.status_code == 404

    def test_ff_not_enabled(self):
        response = self._make_request()
        assert response.status_code == 404

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    @patch.object(BatchNumberFilter, 'options', [("b001", "b001")])
    def test_success(self):
        response = self._make_request()
        assert response.status_code == 200


@es_test(requires=[case_search_adapter], setup_class=True)
class TestPaymentsVerifyTableView(BaseTestPaymentsView):
    urlname = PaymentsVerificationTableView.urlname

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.factory = CaseFactory(cls.domain)
        cls.case_list = [
            _create_case(
                cls.factory,
                name='foo',
                data={
                    'batch_number': 'B001',
                    'email': 'bsmith@example.org',
                    'phone_number': '0987654321',
                    'amount': '100',
                    'currency': 'Dollar',
                    'payee_note': 'Jan payment',
                    'payer_message': 'Thanks',
                }),
            _create_case(
                cls.factory,
                name='bar',
                data={
                    'batch_number': 'B001',
                    'phone_number': '0987654322',
                }),
        ]
        case_search_adapter.bulk_index(cls.case_list, refresh=True)

    @classmethod
    def tearDownClass(cls):
        for case in cls.case_list:
            case.delete()
        super().tearDownClass()

    def test_not_logged_in(self):
        response = self._make_request(log_in=False)
        self.assertRedirects(response, f'/accounts/login/?next={self.endpoint}')

    def test_ff_not_enabled(self):
        response = self._make_request()
        assert response.status_code == 404

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_success(self):
        response = self._make_request()
        assert response.status_code == 200

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_response_data_rows(self):
        response = self._make_request()
        queryset = response.context['table'].data
        assert len(queryset) == 2
        for row in queryset:
            if row.record.get('case_id') == self.case_list[0].case_id:
                assert row.record.case.case_json == {
                    'batch_number': 'B001',
                    'email': 'bsmith@example.org',
                    'phone_number': '0987654321',
                    'amount': '100',
                    'currency': 'Dollar',
                    'payee_note': 'Jan payment',
                    'payer_message': 'Thanks',
                }
            else:
                assert row.record.case.case_json == {
                    'batch_number': 'B001',
                    'phone_number': '0987654322',
                }

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_verify_rows(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(
            self.endpoint,
            data={
                'selected_ids': [case.case_id for case in self.case_list],
            },
            headers={'HQ-HX-Action': 'verify_rows'},
        )
        assert response.status_code == 200
        assert response.context['success_count'] == 2
        assert response.context['failure_count'] == 0


@es_test(requires=[case_search_adapter], setup_class=True)
class TestPaymentsVerifyTableFilterView(BaseTestPaymentsView):
    urlname = PaymentsVerificationTableView.urlname

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.factory = CaseFactory(cls.domain)
        cls.case_list = [
            _create_case(
                cls.factory,
                name='foo',
                data={
                    PaymentProperties.BATCH_NUMBER: 'B001',
                    PaymentProperties.PAYMENT_VERIFIED: True,
                    PaymentProperties.PAYMENT_SUBMITTED: True,
                }),
            _create_case(
                cls.factory,
                name='bar',
                data={
                    PaymentProperties.BATCH_NUMBER: 'B001',
                    PaymentProperties.PAYMENT_VERIFIED: True,
                    PaymentProperties.PAYMENT_SUBMITTED: False,
                }),
            _create_case(
                cls.factory,
                name='baz',
                data={
                    PaymentProperties.BATCH_NUMBER: 'B001',
                }),
        ]
        case_search_adapter.bulk_index(cls.case_list, refresh=True)

    @classmethod
    def tearDownClass(cls):
        for case in cls.case_list:
            case.delete()
        super().tearDownClass()

    def test_ff_not_enabled(self):
        response = self._make_request()
        assert response.status_code == 404

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_verification_status_filter_verified_has_two(self):
        response = self._make_request(querystring='payment_verification_status=verified')
        queryset = response.context['table'].data
        assert len(queryset) == 2

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_verification_status_filter_unverified_has_one(self):
        response = self._make_request(querystring='payment_verification_status=unverified')
        queryset = response.context['table'].data
        assert len(queryset) == 1

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_verification_status_filter_unfiltered(self):
        response = self._make_request(querystring='payment_verification_status=')
        queryset = response.context['table'].data
        assert len(queryset) == 3

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_batch_number_filter_has_none(self):
        response = self._make_request(querystring='batch_number=9999')
        queryset = response.context['table'].data
        assert len(queryset) == 0

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_batch_number_filter_has_three(self):
        response = self._make_request(querystring='batch_number=B001')
        queryset = response.context['table'].data
        assert len(queryset) == 3

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_batch_number_filter_no_value_has_three(self):
        response = self._make_request(querystring='batch_number=')
        queryset = response.context['table'].data
        assert len(queryset) == 3

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_payment_status_filter_submitted_payments_has_one(self):
        response = self._make_request(querystring='payment_status=submitted')
        queryset = response.context['table'].data
        assert len(queryset) == 1

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_payment_status_filter_not_submitted_payments_has_one(self):
        response = self._make_request(querystring='payment_status=not_submitted')
        queryset = response.context['table'].data
        assert len(queryset) == 1

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_payment_status_filter_failed_payments_has_one(self):
        response = self._make_request(querystring='payment_status=submission_failed')
        queryset = response.context['table'].data
        assert len(queryset) == 1


class TestPaymentsConfigurationView(BaseTestPaymentsView):
    urlname = PaymentConfigurationView.urlname

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connection_settings = ConnectionSettings.objects.create(
            domain=cls.domain,
            name='test-conn-settings',
            username='test-username',
            password='test-password',
            url='http://test-url.com',
        )

    def test_not_logged_in(self):
        response = self._make_request(log_in=False)
        assert response.status_code == 404

    def test_ff_not_enabled(self):
        response = self._make_request()
        assert response.status_code == 404

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_success_get(self, *args):
        response = self._make_request()
        assert response.status_code == 200

        form_fields = response.context[0].get('payments_config_form').fields
        assert form_fields['connection_settings'].choices == [(self.connection_settings.id, 'test-conn-settings')]
        assert form_fields['environment'].choices == [('sandbox', 'Sandbox'), ('live', 'Live')]

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_success_create(self, *args):
        assert not MoMoConfig.objects.filter(domain=self.domain)

        post_data = {
            'connection_settings': self.connection_settings.id,
            'environment': 'live',
        }
        self.client.login(username=self.username, password=self.password)
        self.client.post(self.endpoint, data=post_data)

        payment_config = MoMoConfig.objects.get(domain=self.domain)
        assert payment_config.connection_settings_id == self.connection_settings.id
        assert payment_config.environment == 'live'


def _create_case(factory, name, data):
    return factory.create_case(
        case_name=name,
        case_type=MOMO_PAYMENT_CASE_TYPE,
        update=data
    )
