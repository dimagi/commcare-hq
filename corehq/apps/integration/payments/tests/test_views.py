from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseFactory
from corehq.apps.case_importer.const import MOMO_PAYMENT_CASE_TYPE

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.groups import group_adapter
from corehq.apps.es.users import user_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.integration.kyc.models import KycVerificationStatus, UserDataStore, KycConfig
from corehq.apps.integration.payments.const import PaymentProperties, PaymentStatus
from corehq.apps.integration.payments.models import MoMoConfig
from corehq.apps.integration.payments.views import (
    PaymentsVerificationReportView,
    PaymentsVerificationTableView,
    PaymentConfigurationView,
)
from corehq.apps.reports.filters.case_list import CaseListFilter as EMWF
from corehq.apps.users.models import WebUser, HqPermissions
from corehq.apps.users.models_role import UserRole
from corehq.apps.users.permissions import PAYMENTS_REPORT_PERMISSION
from corehq.motech.models import ConnectionSettings
from corehq.util.test_utils import flag_enabled
from corehq.apps.integration.payments.filters import BatchNumberFilter, PaymentVerifiedByFilter


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

        cls.user_without_access = cls.make_user_with_custom_role('test-user2', 'payments-no-access')
        cls.user_with_access = cls.make_user_with_custom_role('test-user3', 'payments-access', True)

    @classmethod
    def make_user_with_custom_role(cls, username, role_name, has_payments_access=False):
        user = WebUser.create(
            domain=cls.domain,
            username=username,
            password=cls.password,
            created_by=None,
            created_via=None
        )
        view_report_list = [PAYMENTS_REPORT_PERMISSION] if has_payments_access else []
        role = UserRole.create(
            domain=cls.domain,
            name=role_name,
            permissions=HqPermissions(view_report_list=view_report_list),
        )
        user.set_role(cls.domain, role.get_qualified_id())
        user.save()
        return user

    @classmethod
    def tearDownClass(cls):
        cls.webuser.delete(None, None)
        cls.user_without_access.delete(None, None)
        cls.user_with_access.delete(None, None)
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
    def test_user_without_access(self):
        self.client.login(username=self.user_without_access.username, password=self.password)
        response = self.client.get(self.endpoint)
        assert response.status_code == 403

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    @patch.object(BatchNumberFilter, 'options', [("b001", "b001")])
    @patch.object(PaymentVerifiedByFilter, 'options', [('test-user', 'test-user')])
    def test_user_with_access(self):
        self.client.login(username=self.user_with_access.username, password=self.password)
        response = self.client.get(self.endpoint)
        assert response.status_code == 200

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    @patch.object(BatchNumberFilter, 'options', [("b001", "b001")])
    @patch.object(PaymentVerifiedByFilter, 'options', [('test-user', 'test-user')])
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
        cls.case_linked_to_payment_case = cls.factory.create_case(
            case_name='test_case',
            case_type='test',
            update={
                'kyc_verification_status': KycVerificationStatus.PASSED,
            }
        )
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
                    PaymentProperties.USER_OR_CASE_ID: cls.case_linked_to_payment_case.case_id,
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
        self.assertRedirects(response, f"{self.login_endpoint}?next={self.endpoint}")

    def test_ff_not_enabled(self):
        response = self._make_request()
        assert response.status_code == 404

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_user_without_access(self):
        self.client.login(username=self.user_without_access.username, password=self.password)
        response = self.client.get(self.endpoint)
        assert response.status_code == 403

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_user_with_access(self):
        self.client.login(username=self.user_with_access.username, password=self.password)
        response = self.client.get(self.endpoint)
        assert response.status_code == 200

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
                    PaymentProperties.USER_OR_CASE_ID: self.case_linked_to_payment_case.case_id,
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

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_verification_invalid_status(self):
        submitted_case = _create_case(
            self.factory,
            name='submitted_case',
            data={
                PaymentProperties.PAYMENT_VERIFIED: 'True',
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUBMITTED,
            }
        )
        self.addCleanup(submitted_case.delete)

        self.client.login(username=self.username, password=self.password)
        response = self.client.post(
            self.endpoint,
            data={'selected_ids': [submitted_case.case_id]},
            headers={'HQ-HX-Action': 'verify_rows'},
        )

        assert response.status_code == 400
        assert (
            b"Only payments in 'Not Verified' or 'Request failed' state are eligible for verification."
            in response.content
        )

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_verification_no_cases(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(
            self.endpoint,
            data={'selected_ids': []},
            headers={'HQ-HX-Action': 'verify_rows'},
        )

        assert response.status_code == 400
        assert b"One or more case IDs are required for verification." in response.content

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_verification_limit_crossed(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(
            self.endpoint,
            data={'selected_ids': ['abcd'] * 101},
            headers={'HQ-HX-Action': 'verify_rows'},
        )

        assert response.status_code == 400
        limit = PaymentsVerificationTableView.VERIFICATION_ROWS_LIMIT
        assert "You can only verify for up to {} cases at a time.".format(limit) in str(response.content)

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_verification_status(self):
        response = self._make_request()

        # no kyc config
        assert response.context_data['user_or_cases_verification_statuses'] == {}

        KycConfig.objects.create(
            domain=self.domain,
            user_data_store=UserDataStore.OTHER_CASE_TYPE,
            api_field_to_user_data_map=[],
            other_case_type="test",
        )
        response = self._make_request()

        assert response.context_data['user_or_cases_verification_statuses'] == {
            self.case_linked_to_payment_case.case_id: KycVerificationStatus.PASSED
        }

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_revert_verification_success(self):
        verified_case = _create_case(
            self.factory,
            name='verified_case',
            data={
                PaymentProperties.PAYMENT_VERIFIED: 'True',
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.PENDING_SUBMISSION,
                PaymentProperties.PAYMENT_VERIFIED_BY: 'test_user',
                PaymentProperties.PAYMENT_VERIFIED_BY_USER_ID: 'test_user_id',
                PaymentProperties.PAYMENT_VERIFIED_ON_UTC: '2024-01-01',
            }
        )
        self.addCleanup(verified_case.delete)

        self.client.login(username=self.username, password=self.password)
        response = self.client.post(
            self.endpoint,
            data={'selected_ids': [verified_case.case_id]},
            headers={'HQ-HX-Action': 'revert_verification'},
        )

        assert response.status_code == 200
        verified_case.refresh_from_db()
        case_json = verified_case.case_json
        assert case_json[PaymentProperties.PAYMENT_VERIFIED] == 'False'
        assert case_json[PaymentProperties.PAYMENT_STATUS] == PaymentStatus.NOT_VERIFIED
        assert case_json[PaymentProperties.PAYMENT_VERIFIED_BY] == ''
        assert case_json[PaymentProperties.PAYMENT_VERIFIED_BY_USER_ID] == ''
        assert case_json[PaymentProperties.PAYMENT_VERIFIED_ON_UTC] == ''

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_revert_verification_invalid_status(self):
        submitted_case = _create_case(
            self.factory,
            name='submitted_case',
            data={
                PaymentProperties.PAYMENT_VERIFIED: 'True',
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUBMITTED,
            }
        )
        self.addCleanup(submitted_case.delete)

        self.client.login(username=self.username, password=self.password)
        response = self.client.post(
            self.endpoint,
            data={'selected_ids': [submitted_case.case_id]},
            headers={'HQ-HX-Action': 'revert_verification'},
        )

        assert response.status_code == 400
        assert (b"Only payments in the 'Pending Submission' state are eligible for verification reversal."
                in response.content)

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_revert_verification_no_cases(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(
            self.endpoint,
            data={'selected_ids': []},
            headers={'HQ-HX-Action': 'revert_verification'},
        )

        assert response.status_code == 400
        assert b"One or more case IDs are required to revert verification." in response.content

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_revert_verification_limit_crossed(self):

        self.client.login(username=self.username, password=self.password)
        response = self.client.post(
            self.endpoint,
            data={'selected_ids': ['abcd'] * 101},
            headers={'HQ-HX-Action': 'revert_verification'},
        )

        assert response.status_code == 400
        limit = PaymentsVerificationTableView.REVERT_VERIFICATION_ROWS_LIMIT
        assert (
            "You can only revert verification for up to {} cases at a time.".format(limit)
            in str(response.content)
        )


@es_test(requires=[case_search_adapter, user_adapter, group_adapter], setup_class=True)
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
                    PaymentProperties.PAYMENT_STATUS: PaymentStatus.PENDING_SUBMISSION,
                }),
            _create_case(
                cls.factory,
                name='bar',
                data={
                    PaymentProperties.BATCH_NUMBER: 'B001',
                    PaymentProperties.PAYMENT_VERIFIED: True,
                    PaymentProperties.PAYMENT_STATUS: PaymentStatus.REQUEST_FAILED,
                }),
            _create_case(
                cls.factory,
                name='baz',
                data={
                    PaymentProperties.BATCH_NUMBER: 'B001',
                }),
            _create_case(
                cls.factory,
                name='case_owner_test',
                data={
                    PaymentProperties.BATCH_NUMBER: 'B002',
                },
                owner_id=cls.user_with_access.user_id
            )
        ]
        case_search_adapter.bulk_index(cls.case_list, refresh=True)
        user_adapter.bulk_index([cls.webuser, cls.user_without_access, cls.user_with_access], refresh=True)

    @classmethod
    def tearDownClass(cls):
        for case in cls.case_list:
            case.delete()
        super().tearDownClass()

    def test_ff_not_enabled(self):
        response = self._make_request()
        assert response.status_code == 404

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
        assert len(queryset) == 4

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_payment_status_filter_pending_payments_has_one(self):
        response = self._make_request(querystring=f'payment_status={PaymentStatus.PENDING_SUBMISSION}')
        queryset = response.context['table'].data
        assert len(queryset) == 1

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_payment_status_filter_request_failed_payments_has_one(self):
        response = self._make_request(querystring=f'payment_status={PaymentStatus.REQUEST_FAILED}')
        queryset = response.context['table'].data
        assert len(queryset) == 1

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_case_owner_filter(self):
        response = self._make_request(querystring=f'{EMWF.slug}=u__{self.user_with_access.user_id}')
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
    def test_user_without_access(self):
        self.client.login(username=self.user_without_access.username, password=self.password)
        response = self.client.get(self.endpoint)
        assert response.status_code == 403

    @flag_enabled('MTN_MOBILE_WORKER_VERIFICATION')
    def test_user_with_access(self):
        self.client.login(username=self.user_with_access.username, password=self.password)
        response = self.client.get(self.endpoint)
        assert response.status_code == 200

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


def _create_case(factory, name, data, owner_id=None):
    return factory.create_case(
        case_name=name,
        case_type=MOMO_PAYMENT_CASE_TYPE,
        owner_id=owner_id,
        update=data
    )
