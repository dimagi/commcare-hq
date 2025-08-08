import uuid
from unittest.mock import patch

from django.test import TestCase

import pytest

from casexml.apps.case.mock import CaseFactory

from corehq.apps.case_importer.const import MOMO_PAYMENT_CASE_TYPE
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.integration.payments.const import (
    PaymentProperties,
    PaymentStatus,
)
from corehq.apps.integration.payments.exceptions import PaymentRequestError
from corehq.apps.integration.payments.models import MoMoConfig
from corehq.apps.integration.payments.services import (
    _request_payment,
    request_payments_for_cases,
    revert_payment_verification,
    verify_payment_cases,
)
from corehq.apps.users.models import WebUser
from corehq.motech.models import ConnectionSettings


class TestVerifyPaymentCases(TestCase):

    domain = "test-domain"

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

    @classmethod
    def tearDownClass(cls):
        cls.webuser.delete(None, None)
        cls.domain_obj.delete()
        for case in cls.case_list:
            case.delete()

        super().tearDownClass()

    def test_verify_payment_cases(self):
        for case in self.case_list:
            assert PaymentProperties.PAYMENT_VERIFIED not in case.case_json

        case_ids = [case_.case_id for case_ in self.case_list]
        verified_cases = verify_payment_cases(self.domain, case_ids, self.webuser)

        assert len(verified_cases) == 2

        for case in self.case_list:
            case.refresh_from_db()
            assert case.case_json[PaymentProperties.PAYMENT_VERIFIED] == 'True'
            assert case.case_json[PaymentProperties.PAYMENT_VERIFIED_BY] == self.webuser.username
            assert case.case_json[PaymentProperties.PAYMENT_VERIFIED_BY_USER_ID] == self.webuser.user_id
            assert case.case_json[PaymentProperties.PAYMENT_VERIFIED_ON_UTC] is not None

    def test_verify_payments_cases_with_invalid_statuses(self):
        unverified_case = _create_case(
            factory=self.factory,
            name='Not verified case',
            data={
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.PENDING_SUBMISSION,
            }
        )
        self.addCleanup(unverified_case.delete)

        with pytest.raises(
            PaymentRequestError,
            match="Only payments in '{}' or '{}' state are eligible for verification.".format(
                PaymentStatus.NOT_VERIFIED.label,
                PaymentStatus.REQUEST_FAILED.label
            )
        ):
            verify_payment_cases(self.domain, [unverified_case.case_id], self.webuser)


class TestPaymentRequest(TestCase):
    domain = "test-domain"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = CaseFactory(cls.domain)
        connection_settings = ConnectionSettings.objects.create(
            domain=cls.domain,
            name='test-conn-settings',
            username='test-username',
            password='test-password',
            url='http://test-url.com',
        )
        cls.config = MoMoConfig.objects.create(
            domain=cls.domain,
            connection_settings=connection_settings,
            environment='sandbox',
        )
        cls.case_list = []

    @classmethod
    def tearDownClass(cls):
        cls.config.delete()
        for case in cls.case_list:
            case.delete()
        super().tearDownClass()

    def test_case_not_verified(self):
        unverified_case = _create_case(
            self.factory,
            name='foo',
            data={**self._payment_details}
        )
        self._add_cleanup(unverified_case)

        with pytest.raises(PaymentRequestError, match="Payment has not been verified"):
            _request_payment(unverified_case, self.config)

    def test_duplicate_payment_request(self):
        previously_submitted_case = _create_case(
            self.factory,
            name='foo',
            data={
                PaymentProperties.PAYMENT_VERIFIED: True,
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUBMITTED,
                **self._payment_details,
            }
        )
        self._add_cleanup(previously_submitted_case)

        with pytest.raises(PaymentRequestError, match="Payment has already been requested"):
            _request_payment(previously_submitted_case, self.config)

    def test_verified_payment_with_missing_data(self):
        verified_case_with_missing_data = _create_case(
            self.factory,
            name='foo',
            data={
                PaymentProperties.PAYMENT_VERIFIED: True,
                PaymentProperties.BATCH_NUMBER: 'B001',
                PaymentProperties.AMOUNT: '100',
                PaymentProperties.CURRENCY: 'Dollar',
                PaymentProperties.PAYEE_NOTE: 'Jan payment',
                PaymentProperties.PAYER_MESSAGE: 'Thanks',
            }
        )
        self._add_cleanup(verified_case_with_missing_data)
        with pytest.raises(PaymentRequestError, match="Invalid payee details"):
            _request_payment(verified_case_with_missing_data, self.config)

    @patch('corehq.apps.integration.payments.services._make_payment_request')
    def test_successful_payment_request(self, make_payment_request_mock):
        make_payment_request_mock.return_value = str(uuid.uuid4())

        verified_case = _create_case(
            self.factory,
            name='foo',
            data={
                PaymentProperties.PAYMENT_VERIFIED: True,
                **self._payment_details,
            }
        )
        self._add_cleanup(verified_case)
        assert _request_payment(verified_case, self.config) is not None

    def _add_cleanup(self, case):
        self.case_list.append(case)

    @property
    def _payment_details(self):
        return {
            PaymentProperties.BATCH_NUMBER: 'B001',
            PaymentProperties.EMAIL: 'bsmith@example.org',
            PaymentProperties.PHONE_NUMBER: '0987654321',
            PaymentProperties.AMOUNT: '100',
            PaymentProperties.CURRENCY: 'Dollar',
            PaymentProperties.PAYEE_NOTE: 'Jan payment',
            PaymentProperties.PAYER_MESSAGE: 'Thanks',
        }


class TestRequestPaymentsForCases(TestCase):
    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        connection_settings = ConnectionSettings.objects.create(
            domain=cls.domain,
            name='test-conn-settings',
            username='test-username',
            password='test-password',
            url='http://test-url.com',
        )
        cls.config = MoMoConfig.objects.create(
            domain=cls.domain,
            connection_settings=connection_settings,
            environment='sandbox',
        )

        cls.factory = CaseFactory(cls.domain)
        cls.case_list = []

    @classmethod
    def tearDownClass(cls):
        cls.config.delete()
        for case in cls.case_list:
            case.delete()
        super().tearDownClass()

    def _create_payment_case(self, name, properties):
        case, = _create_case(self.factory, name, properties),
        return case

    @property
    def _payment_details(self):
        return {
            PaymentProperties.BATCH_NUMBER: 'B001',
            PaymentProperties.EMAIL: 'bsmith@example.org',
            PaymentProperties.PHONE_NUMBER: '0987654321',
            PaymentProperties.AMOUNT: '100',
            PaymentProperties.CURRENCY: 'Dollar',
            PaymentProperties.PAYEE_NOTE: 'Jan payment',
            PaymentProperties.PAYER_MESSAGE: 'Thanks',
            PaymentProperties.PAYMENT_VERIFIED: 'True',
        }

    @patch('corehq.apps.integration.payments.services._make_payment_request')
    @patch('corehq.apps.integration.payments.services.bulk_update_cases')
    def test_request_payments_for_cases(self, bulk_update_cases_mock, make_payment_request_mock):
        transaction_id = str(uuid.uuid4())
        make_payment_request_mock.return_value = transaction_id

        payment_cases = [
            self._create_payment_case('case 1', self._payment_details),
            self._create_payment_case('case 2', self._payment_details),
        ]
        self.case_list.extend(payment_cases)  # for cleanup
        request_payments_for_cases([_case.case_id for _case in payment_cases], self.config)

        bulk_update_cases_mock.assert_called_once()
        _, payment_updates = bulk_update_cases_mock.call_args[0]
        assert len(payment_updates) == 2

        case_id, payment_property_update, _ = payment_updates[0]
        assert case_id == payment_cases[0].case_id
        assert payment_property_update['transaction_id'] == transaction_id
        assert payment_property_update[PaymentProperties.PAYMENT_STATUS] == PaymentStatus.SUBMITTED
        assert PaymentProperties.PAYMENT_TIMESTAMP in payment_property_update

    @patch('corehq.apps.integration.payments.services._make_payment_request')
    @patch('corehq.apps.integration.payments.services.bulk_update_cases')
    def test_request_payments_for_cases_with_some_missing_data(
        self, bulk_update_cases_mock, make_payment_request_mock
    ):
        transaction_id = str(uuid.uuid4())
        make_payment_request_mock.return_value = transaction_id

        payment_cases = [
            self._create_payment_case('Eligible case', self._payment_details),
            self._create_payment_case(
                'Not eligible case',
                {
                    **self._payment_details,
                    'email': None,
                    'phone_number': None
                }
            ),
        ]
        self.case_list.extend(payment_cases)  # for cleanup

        for payment_case in payment_cases:
            case_data = payment_case.case_json
            assert case_data.get('transaction_id') is None
            assert PaymentProperties.PAYMENT_STATUS not in case_data
            assert PaymentProperties.PAYMENT_TIMESTAMP not in case_data

        request_payments_for_cases([_case.case_id for _case in payment_cases], self.config)

        bulk_update_cases_mock.assert_called_once()
        _, payment_updates = bulk_update_cases_mock.call_args[0]
        assert len(payment_updates) == 2

        case_id, payment_property_update, _ = payment_updates[0]
        eligible_case = payment_cases[0]
        assert case_id == eligible_case.case_id

        case_id, payment_property_update, _ = payment_updates[1]
        non_eligible_case = payment_cases[1]
        assert case_id == non_eligible_case.case_id
        assert 'transaction_id' not in payment_property_update
        assert PaymentProperties.PAYMENT_TIMESTAMP in payment_property_update
        assert payment_property_update[PaymentProperties.PAYMENT_STATUS] == PaymentStatus.REQUEST_FAILED
        assert payment_property_update[PaymentProperties.PAYMENT_ERROR] == 'Invalid payee details'


class TestRevertPaymentVerification(TestCase):
    domain = "test-domain"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = CaseFactory(cls.domain)

    def setUp(self):
        self.verified_case = _create_case(
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
        self.addCleanup(self.verified_case.delete)

    def test_revert_verification_success(self):
        reverted_cases = revert_payment_verification(self.domain, [self.verified_case.case_id])
        assert len(reverted_cases) == 1

        self.verified_case.refresh_from_db()
        case_json = self.verified_case.case_json
        assert case_json[PaymentProperties.PAYMENT_VERIFIED] == 'False'
        assert PaymentStatus.from_value(case_json[PaymentProperties.PAYMENT_STATUS]) == PaymentStatus.NOT_VERIFIED
        assert case_json[PaymentProperties.PAYMENT_VERIFIED_BY] == ''
        assert case_json[PaymentProperties.PAYMENT_VERIFIED_BY_USER_ID] == ''
        assert case_json[PaymentProperties.PAYMENT_VERIFIED_ON_UTC] == ''

    def test_revert_verification_multiple_cases(self):
        verified_case_2 = _create_case(
            self.factory,
            name='verified_case_2',
            data={
                PaymentProperties.PAYMENT_VERIFIED: 'True',
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.PENDING_SUBMISSION,
                PaymentProperties.PAYMENT_VERIFIED_BY: 'test_user',
                PaymentProperties.PAYMENT_VERIFIED_BY_USER_ID: 'test_user_id',
                PaymentProperties.PAYMENT_VERIFIED_ON_UTC: '2024-01-01',
            }
        )
        self.addCleanup(verified_case_2.delete)

        case_ids = [self.verified_case.case_id, verified_case_2.case_id]

        reverted_cases = revert_payment_verification(self.domain, case_ids)

        assert len(reverted_cases) == 2
        for case in [self.verified_case, verified_case_2]:
            case.refresh_from_db()
            case_json = case.case_json
            assert case_json[PaymentProperties.PAYMENT_VERIFIED] == 'False'
            status = PaymentStatus.from_value(case_json[PaymentProperties.PAYMENT_STATUS])
            assert status == PaymentStatus.NOT_VERIFIED
            assert case_json[PaymentProperties.PAYMENT_VERIFIED_BY] == ''
            assert case_json[PaymentProperties.PAYMENT_VERIFIED_BY_USER_ID] == ''
            assert case_json[PaymentProperties.PAYMENT_VERIFIED_ON_UTC] == ''

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

        with pytest.raises(
            PaymentRequestError,
            match="Only payments in the '{}' state are eligible for verification reversal.".format(
                PaymentStatus.PENDING_SUBMISSION.label
            )
        ):
            revert_payment_verification(self.domain, [self.verified_case.case_id, submitted_case.case_id])

    def test_revert_verification_empty_case_ids(self):
        reverted_cases = revert_payment_verification(self.domain, [])
        assert len(reverted_cases) == 0


def _create_case(factory, name, data):
    return factory.create_case(
        case_name=name,
        case_type=MOMO_PAYMENT_CASE_TYPE,
        update=data
    )
