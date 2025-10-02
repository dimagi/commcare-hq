import uuid
from json import JSONDecodeError
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

import pytest
import requests

from casexml.apps.case.mock import CaseFactory

from corehq.apps.case_importer.const import MOMO_PAYMENT_CASE_TYPE
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.integration.payments.const import (
    PaymentStatusErrorCode,
    PaymentProperties,
    PaymentStatus,
    PAYMENT_STATUS_RETRY_MAX_ATTEMPTS,
)
from corehq.apps.integration.payments.exceptions import PaymentRequestError
from corehq.apps.integration.payments.models import MoMoConfig
from corehq.apps.integration.payments.services import (
    _request_payment,
    request_payment_status,
    request_payments_for_cases,
    request_payments_status_for_cases,
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
            match="Verification: Payment status must be one of the following: '{}', '{}'".format(
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
            PaymentProperties.PAYMENT_STATUS: PaymentStatus.PENDING_SUBMISSION,
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
        assert payment_property_update[PaymentProperties.PAYMENT_ERROR] == 'PaymentRequestError'


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
            match="Verification reversal: Payment status must be one of the following: '{}'".format(
                PaymentStatus.PENDING_SUBMISSION.label
            )
        ):
            revert_payment_verification(self.domain, [self.verified_case.case_id, submitted_case.case_id])

    def test_revert_verification_empty_case_ids(self):
        reverted_cases = revert_payment_verification(self.domain, [])
        assert len(reverted_cases) == 0


class TestRequestPaymentStatus(SimpleTestCase):

    def setUp(self):
        # Create mock objects to avoid database dependencies
        self.mock_config = Mock(spec=MoMoConfig)
        self.mock_config.domain = 'test-domain'
        self.mock_config.environment = 'sandbox'

        self.mock_connection_settings = Mock()
        self.mock_config.connection_settings = self.mock_connection_settings

        self.mock_payment_case = Mock()
        self.mock_payment_case.case_id = str(uuid.uuid4())
        self.transaction_id = str(uuid.uuid4())

    def test_successful_payment_status_request(self):
        self.mock_payment_case.get_case_property.return_value = self.transaction_id

        mock_response = Mock()
        mock_response.json.return_value = {
            'status': PaymentStatus.SUCCESSFUL,
            'reason': None
        }

        with patch('corehq.apps.integration.payments.services._make_payment_status_request') as mock_request:
            mock_request.return_value = mock_response

            result = request_payment_status(self.mock_payment_case, self.mock_config)

            expected = {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUCCESSFUL,
                PaymentProperties.PAYMENT_ERROR: '',
            }
            self.assertEqual(result, expected)
            mock_request.assert_called_once_with(self.transaction_id, self.mock_config)

    def test_failed_payment_status_request(self):
        self.mock_payment_case.get_case_property.return_value = self.transaction_id

        mock_response = Mock()
        mock_response.json.return_value = {
            'status': PaymentStatus.FAILED,
            'reason': 'Insufficient funds'
        }

        with patch('corehq.apps.integration.payments.services._make_payment_status_request') as mock_request:
            mock_request.return_value = mock_response

            result = request_payment_status(self.mock_payment_case, self.mock_config)

            expected = {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.FAILED,
                PaymentProperties.PAYMENT_ERROR: 'Insufficient funds',
            }
            self.assertEqual(result, expected)

    def test_no_transaction_id(self):
        """Test error when no transaction ID is found"""
        self.mock_payment_case.get_case_property.return_value = None

        result = request_payment_status(self.mock_payment_case, self.mock_config)

        expected = {
            PaymentProperties.PAYMENT_STATUS: PaymentStatus.ERROR,
            PaymentProperties.PAYMENT_ERROR: 'MissingTransactionId',
        }
        self.assertEqual(result, expected)

    def test_http_error_404(self):
        self.mock_payment_case.get_case_property.return_value = self.transaction_id

        mock_response = Mock()
        mock_response.status_code = 404
        http_error = requests.exceptions.HTTPError(response=mock_response)

        with patch('corehq.apps.integration.payments.services._make_payment_status_request') as mock_request:
            mock_request.side_effect = http_error

            result = request_payment_status(self.mock_payment_case, self.mock_config)

            expected = {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.ERROR,
                PaymentProperties.PAYMENT_ERROR: PaymentStatusErrorCode.HTTP_ERROR_404,
            }
            self.assertEqual(result, expected)

    def test_http_error_500_with_json_response(self):
        self.mock_payment_case.get_case_property.return_value = self.transaction_id

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            'code': 'INTERNAL_PROCESSING_ERROR',
            'message': 'An internal error occurred'
        }
        http_error = requests.exceptions.HTTPError(response=mock_response)

        with patch('corehq.apps.integration.payments.services._make_payment_status_request') as mock_request:
            mock_request.side_effect = http_error

            result = request_payment_status(self.mock_payment_case, self.mock_config)

            expected = {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.ERROR,
                PaymentProperties.PAYMENT_ERROR: 'INTERNAL_PROCESSING_ERROR',
            }
            self.assertEqual(result, expected)

    def test_http_error_500_with_json_decode_error(self):
        self.mock_payment_case.get_case_property.return_value = self.transaction_id

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.side_effect = JSONDecodeError("Expecting value", "", 0)
        http_error = requests.exceptions.HTTPError(response=mock_response)

        with patch('corehq.apps.integration.payments.services._make_payment_status_request') as mock_request:
            mock_request.side_effect = http_error

            result = request_payment_status(self.mock_payment_case, self.mock_config)

            expected = {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.ERROR,
                PaymentProperties.PAYMENT_ERROR: 'HttpError500',
            }
            self.assertEqual(result, expected)

    def test_http_error_502_raises_exception(self):
        self.mock_payment_case.get_case_property.return_value = self.transaction_id

        mock_response = Mock()
        mock_response.status_code = 502
        http_error = requests.exceptions.HTTPError(response=mock_response)

        with patch('corehq.apps.integration.payments.services._make_payment_status_request') as mock_request:
            mock_request.side_effect = http_error

            with pytest.raises(PaymentRequestError, match="Failed to fetch payment status with code: 502"):
                request_payment_status(self.mock_payment_case, self.mock_config)

    @patch('corehq.apps.integration.payments.services.notify_error')
    def test_unexpected_http_error(self, mock_notify_error):
        self.mock_payment_case.get_case_property.return_value = self.transaction_id

        mock_response = Mock()
        mock_response.status_code = 418  # I'm a teapot - unexpected error
        mock_response.text = "I'm a teapot"
        mock_response.json.return_value = {}
        http_error = requests.exceptions.HTTPError(response=mock_response)

        with patch('corehq.apps.integration.payments.services._make_payment_status_request') as mock_request:
            mock_request.side_effect = http_error

            result = request_payment_status(self.mock_payment_case, self.mock_config)

            expected = {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.ERROR,
                PaymentProperties.PAYMENT_ERROR: 'HttpError418',
            }
            self.assertEqual(result, expected)

            # Verify that error notification was called
            mock_notify_error.assert_called_once()
            call_args = mock_notify_error.call_args
            self.assertIn("Unexpected HTTP error 418", call_args[0][0])
            self.assertEqual(call_args[1]['details']['domain'], 'test-domain')
            self.assertEqual(call_args[1]['details']['case_id'], self.mock_payment_case.case_id)

    def test_connection_timeout_error(self):
        self.mock_payment_case.get_case_property.return_value = self.transaction_id

        with patch('corehq.apps.integration.payments.services._make_payment_status_request') as mock_request:
            mock_request.side_effect = requests.exceptions.Timeout("Connection timed out")

            with pytest.raises(
                PaymentRequestError,
                match="Failed to fetch payment status. Unable to connect to server. Please try again later."
            ):
                request_payment_status(self.mock_payment_case, self.mock_config)

    def test_connection_error(self):
        self.mock_payment_case.get_case_property.return_value = self.transaction_id

        with patch('corehq.apps.integration.payments.services._make_payment_status_request') as mock_request:
            mock_request.side_effect = requests.exceptions.ConnectionError("Failed to establish connection")

            with pytest.raises(
                PaymentRequestError,
                match="Failed to fetch payment status. Unable to connect to server. Please try again later."
            ):
                request_payment_status(self.mock_payment_case, self.mock_config)

    @patch('corehq.apps.integration.payments.services.notify_exception')
    def test_unexpected_exception(self, mock_notify_exception):
        self.mock_payment_case.get_case_property.return_value = self.transaction_id

        with patch('corehq.apps.integration.payments.services._make_payment_status_request') as mock_request:
            mock_request.side_effect = ValueError("Unexpected error")

            result = request_payment_status(self.mock_payment_case, self.mock_config)

            expected = {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.ERROR,
                PaymentProperties.PAYMENT_ERROR: 'UnexpectedError',
            }
            self.assertEqual(result, expected)

            # Verify that exception notification was called
            mock_notify_exception.assert_called_once()
            call_args = mock_notify_exception.call_args
            self.assertIn("Unexpected error occurred while fetching status", call_args[0][1])
            self.assertEqual(call_args[1]['details']['domain'], 'test-domain')
            self.assertEqual(call_args[1]['details']['case_id'], self.mock_payment_case.case_id)

    def test_unexpected_status_value(self):
        self.mock_payment_case.get_case_property.return_value = self.transaction_id

        mock_response = Mock()
        mock_response.json.return_value = {
            'status': 'invalid',  # unexpected status
            'reason': 'Processing',
        }

        with patch('corehq.apps.integration.payments.services._make_payment_status_request') as mock_request:
            mock_request.return_value = mock_response

            result = request_payment_status(self.mock_payment_case, self.mock_config)

            expected = {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.ERROR,
                PaymentProperties.PAYMENT_ERROR: 'UnexpectedStatus-invalid',
            }
            self.assertEqual(result, expected)

    def test_status_with_uppercase(self):
        self.mock_payment_case.get_case_property.return_value = self.transaction_id

        mock_response = Mock()
        mock_response.json.return_value = {
            'status': 'SUCCESSFUL',  # uppercase
            'reason': None
        }

        with patch('corehq.apps.integration.payments.services._make_payment_status_request') as mock_request:
            mock_request.return_value = mock_response

            result = request_payment_status(self.mock_payment_case, self.mock_config)

            expected = {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUCCESSFUL,
                PaymentProperties.PAYMENT_ERROR: '',
            }
            self.assertEqual(result, expected)

    def test_successful_status_without_reason(self):
        self.mock_payment_case.get_case_property.return_value = self.transaction_id

        mock_response = Mock()
        mock_response.json.return_value = {
            'status': PaymentStatus.SUCCESSFUL
        }

        with patch('corehq.apps.integration.payments.services._make_payment_status_request') as mock_request:
            mock_request.return_value = mock_response

            result = request_payment_status(self.mock_payment_case, self.mock_config)

            expected = {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUCCESSFUL,
                PaymentProperties.PAYMENT_ERROR: '',
            }
            self.assertEqual(result, expected)

    def test_failed_status_with_reason(self):
        self.mock_payment_case.get_case_property.return_value = self.transaction_id

        mock_response = Mock()
        mock_response.json.return_value = {
            'status': PaymentStatus.FAILED,
            'reason': 'Account blocked'
        }

        with patch('corehq.apps.integration.payments.services._make_payment_status_request') as mock_request:
            mock_request.return_value = mock_response

            result = request_payment_status(self.mock_payment_case, self.mock_config)

            expected = {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.FAILED,
                PaymentProperties.PAYMENT_ERROR: 'Account blocked',
            }
            self.assertEqual(result, expected)


class TestRequestPaymentsStatusForCases(TestCase):

    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = CaseFactory(cls.domain)

        cls.connection_settings = ConnectionSettings.objects.create(
            domain=cls.domain,
            name='test-conn-settings-status',
            username='test-username',
            password='test-password',
            url='http://test-url.com',
        )
        cls.config = MoMoConfig.objects.create(
            domain=cls.domain,
            connection_settings=cls.connection_settings,
            environment='sandbox',
        )

    @classmethod
    def tearDownClass(cls):
        cls.config.delete()
        cls.connection_settings.delete()
        super().tearDownClass()

    def _create_payment_case(self, name, properties):
        case = _create_case(self.factory, name, properties)
        return case

    @patch('corehq.apps.integration.payments.services.request_payment_status')
    def test_request_payments_status_for_cases_success(self, mock_request_status):
        submitted_cases = [
            self._create_payment_case('case_1', {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUBMITTED,
                'transaction_id': str(uuid.uuid4())
            }),
            self._create_payment_case('case_2', {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUBMITTED,
                'transaction_id': str(uuid.uuid4())
            })
        ]
        for case in submitted_cases:
            self.addCleanup(case.delete)

        mock_request_status.side_effect = [
            {PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUCCESSFUL},
            {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.FAILED,
                PaymentProperties.PAYMENT_ERROR: 'DepositPayerFailed',
            }
        ]

        case_ids = [case.case_id for case in submitted_cases]
        request_payments_status_for_cases(case_ids, self.config)

        self.assertEqual(mock_request_status.call_count, 2)

        for case in submitted_cases:
            case.refresh_from_db()
            if case.name == 'case_1':
                self.assertEqual(case.case_json[PaymentProperties.PAYMENT_STATUS], PaymentStatus.SUCCESSFUL)
                self.assertNotIn(PaymentProperties.PAYMENT_ERROR, case.case_json)
            elif case.name == 'case_2':
                self.assertEqual(case.case_json[PaymentProperties.PAYMENT_STATUS], PaymentStatus.FAILED)
                self.assertEqual(case.case_json[PaymentProperties.PAYMENT_ERROR], 'DepositPayerFailed')

    @patch('corehq.apps.integration.payments.services.request_payment_status')
    def test_request_payments_status_for_cases_filters_non_submitted(self, mock_request_status):
        cases = [
            self._create_payment_case('submitted_case', {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUBMITTED,
                'transaction_id': str(uuid.uuid4())
            }),
            self._create_payment_case('pending_case', {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.PENDING_SUBMISSION
            }),
            self._create_payment_case('not_verified_case', {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.NOT_VERIFIED
            }),
            self._create_payment_case('failed_case', {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.REQUEST_FAILED
            })
        ]
        for case in cases:
            self.addCleanup(case.delete)

        mock_request_status.return_value = {PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUCCESSFUL}

        case_ids = [case.case_id for case in cases]
        request_payments_status_for_cases(case_ids, self.config)

        # Only the submitted case should be processed
        mock_request_status.assert_called_once()
        for case in cases:
            case.refresh_from_db()
        self.assertEqual(cases[0].case_json[PaymentProperties.PAYMENT_STATUS], PaymentStatus.SUCCESSFUL)
        self.assertEqual(cases[1].case_json[PaymentProperties.PAYMENT_STATUS], PaymentStatus.PENDING_SUBMISSION)
        self.assertEqual(cases[2].case_json[PaymentProperties.PAYMENT_STATUS], PaymentStatus.NOT_VERIFIED)
        self.assertEqual(cases[3].case_json[PaymentProperties.PAYMENT_STATUS], PaymentStatus.REQUEST_FAILED)

    @patch('corehq.apps.integration.payments.services.request_payment_status')
    def test_request_payments_status_handles_payment_request_errors(self, mock_request_status):
        submitted_cases = [
            self._create_payment_case('case_1', {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUBMITTED,
                'transaction_id': str(uuid.uuid4())
            }),
            self._create_payment_case('case_2', {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUBMITTED,
                'transaction_id': str(uuid.uuid4())
            }),
            self._create_payment_case('case_3', {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUBMITTED,
                'transaction_id': str(uuid.uuid4())
            })
        ]
        for case in submitted_cases:
            self.addCleanup(case.delete)

        mock_request_status.side_effect = [
            {PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUCCESSFUL},
            PaymentRequestError("Network timeout"),
            {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.FAILED,
                PaymentProperties.PAYMENT_ERROR: 'DepositPayerInvalidCurrency',
            }
        ]

        case_ids = [case.case_id for case in submitted_cases]
        request_payments_status_for_cases(case_ids, self.config)

        # All three cases should be called
        self.assertEqual(mock_request_status.call_count, 3)

        for case in submitted_cases:
            case.refresh_from_db()
        self.assertEqual(submitted_cases[0].case_json[PaymentProperties.PAYMENT_STATUS], PaymentStatus.SUCCESSFUL)
        # Case 2 should not be updated due to PaymentRequestError
        self.assertEqual(submitted_cases[1].case_json[PaymentProperties.PAYMENT_STATUS], PaymentStatus.SUBMITTED)
        self.assertEqual(submitted_cases[2].case_json[PaymentProperties.PAYMENT_STATUS], PaymentStatus.FAILED)
        self.assertEqual(
            submitted_cases[2].case_json[PaymentProperties.PAYMENT_ERROR],
            'DepositPayerInvalidCurrency'
        )

    @patch('corehq.apps.integration.payments.services.request_payment_status')
    def test_request_payments_status_for_cases_no_submitted_cases(self, mock_request_status):
        cases = [
            self._create_payment_case('pending_case', {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.PENDING_SUBMISSION
            }),
            self._create_payment_case('not_verified_case', {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.NOT_VERIFIED
            })
        ]
        for case in cases:
            self.addCleanup(case.delete)

        case_ids = [case.case_id for case in cases]
        request_payments_status_for_cases(case_ids, self.config)

        mock_request_status.assert_not_called()

    @patch('corehq.apps.integration.payments.services.request_payment_status')
    def test_request_payments_status_for_cases_mixed_scenarios(self, mock_request_status):
        cases = [
            self._create_payment_case('submitted_success', {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUBMITTED,
                'transaction_id': str(uuid.uuid4())
            }),
            self._create_payment_case('submitted_failed', {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUBMITTED,
                'transaction_id': str(uuid.uuid4())
            }),
            self._create_payment_case('submitted_error', {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUBMITTED,
                'transaction_id': str(uuid.uuid4())
            }),
            self._create_payment_case('pending', {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.PENDING_SUBMISSION
            }),
            self._create_payment_case('not_verified', {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.NOT_VERIFIED
            })
        ]
        for case in cases:
            self.addCleanup(case.delete)

        mock_request_status.side_effect = [
            {PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUCCESSFUL},
            {
                PaymentProperties.PAYMENT_STATUS: PaymentStatus.FAILED,
                PaymentProperties.PAYMENT_ERROR: 'DepositPayerNotAllowed',
            },
            PaymentRequestError("Timeout")
        ]

        case_ids = [case.case_id for case in cases]
        request_payments_status_for_cases(case_ids, self.config)

        # Should be called 3 times (only for submitted cases)
        self.assertEqual(mock_request_status.call_count, 3)

        for case in cases:
            case.refresh_from_db()

        self.assertEqual(cases[0].case_json[PaymentProperties.PAYMENT_STATUS], PaymentStatus.SUCCESSFUL)
        self.assertEqual(cases[1].case_json[PaymentProperties.PAYMENT_STATUS], PaymentStatus.FAILED)
        self.assertEqual(cases[1].case_json[PaymentProperties.PAYMENT_ERROR], 'DepositPayerNotAllowed')
        # Case with PaymentRequestError should not be updated
        self.assertEqual(cases[2].case_json[PaymentProperties.PAYMENT_STATUS], PaymentStatus.SUBMITTED)
        # Non-submitted cases should remain unchanged
        self.assertEqual(cases[3].case_json[PaymentProperties.PAYMENT_STATUS], PaymentStatus.PENDING_SUBMISSION)
        self.assertEqual(cases[4].case_json[PaymentProperties.PAYMENT_STATUS], PaymentStatus.NOT_VERIFIED)

    @patch('corehq.apps.integration.payments.services.request_payment_status')
    def test_pending_payment_exceeds_retry_count(self, mock_request_status):
        case = self._create_payment_case('pending_exceed', {
            PaymentProperties.PAYMENT_STATUS: PaymentStatus.PENDING_PROVIDER,
            'transaction_id': str(uuid.uuid4()),
            PaymentProperties.PAYMENT_STATUS_ATTEMPT_COUNT: PAYMENT_STATUS_RETRY_MAX_ATTEMPTS + 1,
        })
        self.addCleanup(case.delete)

        mock_request_status.return_value = {
            PaymentProperties.PAYMENT_STATUS: PaymentStatus.PENDING_PROVIDER,
            PaymentProperties.PAYMENT_ERROR: PaymentStatusErrorCode.DEPOSIT_PAYER_ONGOING,
        }

        request_payments_status_for_cases([case.case_id], self.config)

        case.refresh_from_db()
        self.assertEqual(case.case_json[PaymentProperties.PAYMENT_STATUS], PaymentStatus.ERROR)
        self.assertEqual(
            case.case_json[PaymentProperties.PAYMENT_ERROR],
            PaymentStatusErrorCode.MaxRetryExceededPendingStatus
        )

    @patch('corehq.apps.integration.payments.services.request_payment_status')
    def test_request_error_exceeds_retry_count(self, mock_request_status):
        case = self._create_payment_case('request_error_exceed', {
            PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUBMITTED,
            'transaction_id': str(uuid.uuid4()),
            PaymentProperties.PAYMENT_STATUS_ATTEMPT_COUNT: PAYMENT_STATUS_RETRY_MAX_ATTEMPTS + 1,

        })
        self.addCleanup(case.delete)

        mock_request_status.side_effect = PaymentRequestError('Simulated network failure')

        case_ids = [case.case_id]
        request_payments_status_for_cases(case_ids, self.config)

        case.refresh_from_db()
        self.assertEqual(case.case_json[PaymentProperties.PAYMENT_STATUS], PaymentStatus.ERROR)
        self.assertEqual(
            case.case_json[PaymentProperties.PAYMENT_ERROR],
            PaymentStatusErrorCode.MaxRetryExceededRequestError
        )


def _create_case(factory, name, data):
    return factory.create_case(
        case_name=name,
        case_type=MOMO_PAYMENT_CASE_TYPE,
        update=data
    )
