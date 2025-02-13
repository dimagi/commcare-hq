from django.test import TestCase

from corehq.apps.integration.kyc.models import KycConfig, UserDataStore
from corehq.apps.integration.kyc.services import _get_requests
import doctest

import jsonschema
import pytest

from corehq.apps.integration.kyc.services import _validate_schema
from corehq.motech.models import ConnectionSettings
from corehq.motech.requests import Requests

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


class TestGetRequests(TestCase):

    def test_get_requests(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.USER_CASE,
        )
        assert ConnectionSettings.objects.count() == 0

        # Creates ConnectionSettings
        requests = _get_requests(DOMAIN, config)
        assert isinstance(requests, Requests)
        assert ConnectionSettings.objects.count() == 1

        # Gets existing ConnectionSettings
        requests = _get_requests(DOMAIN, config)
        assert isinstance(requests, Requests)
        assert ConnectionSettings.objects.count() == 1

    def test_bad_config(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.USER_CASE,
            provider='invalid',
        )
        with pytest.raises(ValueError):
            _get_requests(DOMAIN, config)
