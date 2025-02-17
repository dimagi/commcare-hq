import doctest

from django.test import TestCase

import jsonschema
import pytest

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.integration.kyc.models import KycConfig, UserDataStore
from corehq.apps.integration.kyc.services import (
    _get_source_data,
    _validate_schema,
)
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.tests.utils import create_case

DOMAIN = 'test-domain'


def test_doctests():
    import corehq.apps.integration.kyc.services as module
    results = doctest.testmod(module)
    assert results.failed == 0


class TestSaveResult(TestCase):
    # TODO: ...
    pass


class TestGetSourceData(TestCase):

    def setUp(self):
        self.commcare_user = CommCareUser.create(
            DOMAIN, f'test.user@{DOMAIN}.commcarehq.org', 'Passw0rd!',
            None, None,
            user_data={'custom_field': 'custom_value'},
        )
        self.addCleanup(self.commcare_user.delete, DOMAIN, deleted_by=None)
        self.user_case = create_case(
            DOMAIN,
            case_type=USERCASE_TYPE,
            user_id=self.commcare_user._id,
            name='test.user',
            external_id=self.commcare_user._id,
            save=True,
            case_json={'user_case_property': 'user_case_value'},
        )
        self.other_case = create_case(
            DOMAIN,
            case_type='other_case_type',
            save=True,
            case_json={'other_case_property': 'other_case_value'},
        )

    def test_custom_user_data(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.CUSTOM_USER_DATA,
        )
        source_data = _get_source_data(self.commcare_user, config)
        assert source_data == {
            'custom_field': 'custom_value',
            'commcare_profile': '',
        }

    def test_user_case(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.USER_CASE,
        )
        source_data = _get_source_data(self.commcare_user, config)
        assert source_data == {'user_case_property': 'user_case_value'}

    def test_other_case_type(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.OTHER_CASE_TYPE,
            other_case_type='other_case_type',
        )
        source_data = _get_source_data(self.other_case, config)
        assert source_data == {'other_case_property': 'other_case_value'}


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
