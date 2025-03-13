import doctest
from unittest.mock import patch, Mock

import requests
from django.test import TestCase

import jsonschema
import pytest

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.integration.kyc.models import KycConfig, UserDataStore, KycUser, KycVerificationStatus, \
    KycVerificationFailureCause
from corehq.apps.integration.kyc.exceptions import UserCaseNotFound
from corehq.apps.integration.kyc.services import (
    _validate_schema,
    get_user_data_for_api,
    verify_user,
)
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.tests.utils import create_case

DOMAIN = 'test-domain'


def test_doctests():
    import corehq.apps.integration.kyc.services as module
    results = doctest.testmod(module)
    assert results.failed == 0


class TestValidateSchema(TestCase):

    def test_valid_schema(self):
        endpoint = 'kycVerify/v1'
        data = {
            'firstName': 'John',
            'lastName': 'Doe',
            'phoneNumber': '27650600900',
            'emailAddress': 'john.doe@email.com',
            'nationalIdNumber': '123456789',
            'streetAddress': '1st Park Avenue, Mzansi, Johannesburg',
            'city': 'Johannesburg',
            'postCode': '20200',
            'country': 'South Africa',
        }
        _validate_schema(endpoint, data)  # Should not raise an exception

    def test_invalid_schema(self):
        endpoint = 'kycVerify/v1'
        data = {
            'firstName': 'John',
            'lastName': 'Doe',
            # Missing required fields
        }
        with pytest.raises(jsonschema.ValidationError):
            _validate_schema(endpoint, data)


class BaseKycUserSetup(TestCase):
    domain = 'test-kyc-integration'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.user = CommCareUser.create(
            self.domain, 'test-kyc', '123',
            None, None,
            first_name='abc',
        )
        self.config = KycConfig.objects.create(
            domain=self.domain,
            user_data_store=UserDataStore.CUSTOM_USER_DATA,
            api_field_to_user_data_map=self._sample_api_field_to_user_data_map(),
        )
        self.kyc_user = KycUser(self.config, self.user)

    def tearDown(self):
        self.user.delete(self.domain, None)
        self.config.delete()
        super().tearDown()

    def _sample_api_field_to_user_data_map(self):
        return {
            # API Field : User data
            "first_name": "first_name",
            "nationality": "nationality",
        }


class TestGetUserDataForAPI(BaseKycUserSetup):

    def test_custom_user_data_store(self):
        self.user.get_user_data(self.domain).update({'nationality': 'Indian'})
        result = get_user_data_for_api(self.kyc_user, self.config)
        self.assertEqual(result, {'first_name': 'abc', 'nationality': 'Indian'})

    def test_unsafe_custom_user_data_store(self):
        self.config.api_field_to_user_data_map = {
            # API field : Custom user data / CommCareUser property
            "first_name": "password",
        }
        result = get_user_data_for_api(self.kyc_user, self.config)
        self.assertEqual(result, {})

    def test_custom_user_data_store_with_no_data(self):
        result = get_user_data_for_api(self.kyc_user, self.config)
        self.assertEqual(result, {'first_name': 'abc'})

    def test_user_case_data_store(self):
        self.config.user_data_store = UserDataStore.USER_CASE
        self.config.save()
        case = create_case(
            self.domain,
            case_type=USERCASE_TYPE,
            external_id=self.user.user_id,
            save=True,
            case_json={'nationality': 'German'}
        )
        self.addCleanup(case.delete)

        result = get_user_data_for_api(self.kyc_user, self.config)
        self.assertEqual(result, {'first_name': 'abc', 'nationality': 'German'})

    def test_user_case_data_store_with_no_case(self):
        self.config.user_data_store = UserDataStore.USER_CASE
        self.config.save()

        with self.assertRaises(UserCaseNotFound):
            get_user_data_for_api(self.kyc_user, self.config)

    def test_custom_case_data_store(self):
        self.config.user_data_store = UserDataStore.OTHER_CASE_TYPE
        self.config.other_case_type = 'other-case'
        self.config.save()
        case = create_case(
            self.domain,
            case_type='other-case',
            save=True,
            case_json={'first_name': 'abc', 'nationality': 'Dutch'}
        )
        self.addCleanup(case.delete)
        kyc_user = KycUser(self.config, case)

        result = get_user_data_for_api(kyc_user, self.config)
        self.assertEqual(result, {'first_name': 'abc', 'nationality': 'Dutch'})

    def test_custom_case_data_store_with_no_data(self):
        self.config.user_data_store = UserDataStore.OTHER_CASE_TYPE
        self.config.other_case_type = 'other-case'
        self.config.save()
        case = create_case(self.domain, case_type='other-case', save=True)
        self.addCleanup(case.delete)
        kyc_user = KycUser(self.config, case)

        result = get_user_data_for_api(kyc_user, self.config)
        self.assertEqual(result, {})

    def test_incorrect_mapping_standard_field(self):
        api_field_to_user_data_map = self._sample_api_field_to_user_data_map()
        api_field_to_user_data_map['first_name'] = 'wrong-standard_field'
        self.config.api_field_to_user_data_map = api_field_to_user_data_map
        self.config.save()

        result = get_user_data_for_api(self.kyc_user, self.config)

        self.assertEqual(result, {})


class TestVerifyUser(BaseKycUserSetup):

    def _sample_response_json(self):
        return {
            'data': {
                "firstName": 100,
                "lastName": 100,
                "phoneNumber": 100,
                "emailAddress": 100,
                "nationalIdNumber": 100,
                "streetAddress": 100,
                "city": 100,
                "postCode": 100,
                "country": 100,
            }
        }

    @patch('corehq.apps.integration.kyc.services._validate_schema', return_value=True)
    @patch('corehq.apps.integration.kyc.services.get_user_data_for_api', return_value={'phoneNumber': 1234})
    @patch('corehq.motech.requests.Requests.post')
    def test_kyc_success(self, mock_post, *args):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self._sample_response_json()
        mock_post.return_value = mock_response

        verification_status, error = verify_user(self.kyc_user, self.config)

        assert verification_status == KycVerificationStatus.PASSED
        assert error is None

    @patch('corehq.apps.integration.kyc.services._validate_schema', return_value=True)
    @patch('corehq.apps.integration.kyc.services.get_user_data_for_api', return_value={'phoneNumber': 1234})
    @patch('corehq.motech.requests.Requests.post')
    def test_kyc_failed(self, mock_post, *args):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self._sample_response_json()
        mock_response.json.return_value['data'].update({'phoneNumber': 10})  # below threshold
        mock_post.return_value = mock_response

        verification_status, error = verify_user(self.kyc_user, self.config)

        assert verification_status == KycVerificationStatus.FAILED
        assert error == KycVerificationFailureCause.USER_INFORMATION_MISMATCH.value

    @patch('corehq.apps.integration.kyc.services._validate_schema', return_value=True)
    @patch('corehq.apps.integration.kyc.services.get_user_data_for_api', return_value={'phoneNumber': 1234})
    @patch('corehq.motech.requests.Requests.post')
    def test_api_error(self, mock_post, *args):
        mock_post.side_effect = requests.HTTPError

        verification_status, error = verify_user(self.kyc_user, self.config)
        assert error == KycVerificationFailureCause.API_ERROR.value
