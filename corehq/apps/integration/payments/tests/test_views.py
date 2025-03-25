from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseFactory
from corehq.apps.case_importer.const import MOMO_PAYMENT_CASE_TYPE

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.integration.payments.models import MoMoConfig
from corehq.apps.integration.payments.views import (
    PaymentsVerificationReportView,
    PaymentsVerificationTableView,
    PaymentConfigurationView,
)
from corehq.apps.users.models import WebUser
from corehq.motech.models import ConnectionSettings
from corehq.util.test_utils import flag_enabled


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

    def _make_request(self, log_in=True):
        if log_in:
            self.client.login(username=self.username, password=self.password)
        return self.client.get(self.endpoint)


class TestPaymentsVerificationReportView(BaseTestPaymentsView):
    urlname = PaymentsVerificationReportView.urlname

    def test_not_logged_in(self):
        response = self._make_request(log_in=False)
        assert response.status_code == 404

    def test_ff_not_enabled(self):
        response = self._make_request()
        assert response.status_code == 404

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_success(self):
        response = self._make_request()
        assert response.status_code == 200


@es_test(requires=[case_search_adapter], setup_class=True)
class TestPaymentsVerifyTableView(BaseTestPaymentsView):
    urlname = PaymentsVerificationTableView.urlname

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        factory = CaseFactory(cls.domain)
        cls.case_list = [
            _create_case(
                factory,
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
                factory,
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
