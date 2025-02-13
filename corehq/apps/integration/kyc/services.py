import json
import os
import re

import jsonschema
from django.conf import settings
from django.utils.text import camel_case_to_spaces

from corehq.apps.integration.kyc.models import (
    KycConfig,
    KycProviders,
    UserDataStore,
)
from corehq.motech.const import OAUTH2_CLIENT
from corehq.motech.models import ConnectionSettings

CONNECTION_SETTINGS_NAME = 'Chenosis MTN KYC'


class UserCaseNotFound(Exception):
    pass


def verify_user(domain, source):
    """
    Verify a user using the Chenosis MTN KYC API.

    Returns a tuple of ``(verified_okay, bad_fields)`` where
    ``verified_okay`` is a boolean indicating whether the user was
    verified successfully, and ``bad_fields`` is a list of fields that
    failed verification.
    """
    # Documentation: https://apiportal.chenosis.io/en/apis/kyc-verify#endpoints
    #
    # Example request:
    #
    #     POST https://dev.api.chenosis.io/kycVerify/v1/customers/{customerId}
    #     {
    #         "firstName": "John",
    #         "lastName": "Doe",
    #         "phoneNumber": "27650600900",
    #         "emailAddress": "john.doe@email.com",
    #         "nationalIdNumber": "123456789",
    #         "streetAddress": "1st Park Avenue, Mzansi, Johannesburg",
    #         "city": "Johannesburg",
    #         "postCode": "20200",
    #         "country": "South Africa"
    #     }
    #
    # Example 200 response:
    #
    #     {
    #         "statusCode": "0000",
    #         "statusMessage": "Success.",
    #         "customerId": "27650600900",
    #         "transactionId": "232TXYZ-212",
    #         "data": {
    #             "firstName": 100,
    #             "lastName": 100,
    #             "phoneNumber": 100,
    #             "emailAddress": 100,
    #             "nationalIdNumber": 100,
    #             "streetAddress": 100,
    #             "city": 100,
    #             "postCode": 100,
    #             "country": 100
    #         }
    #     }

    # TODO: Determine what thresholds we want
    success_thresholds = {
        'firstName': 100,
        'lastName': 100,
        'phoneNumber': 100,
        'emailAddress': 100,
        'nationalIdNumber': 100,
        'streetAddress': 80,  # Allow streetAddress to be less accurate
        'city': 100,
        'postCode': 100,
        'country': 0,  # e.g "Ivory Coast" vs. "Republic of Côte d'Ivoire" vs. "CIV"?
    }

    kyc_config = KycConfig.objects.get(domain=domain)
    user_data = get_user_data_for_api(source, kyc_config)
    _validate_schema('kycVerify/v1', user_data)
    requests = _get_requests(domain, kyc_config)
    response = requests.post(
        f'/kycVerify/v1/customers/{user_data["phoneNumber"]}',
        json=user_data,
    )
    response.raise_for_status()
    # TODO: Is this what we want to return?
    field_scores = response.json().get('data', {})
    bad_fields = [k for k, v in field_scores if v < success_thresholds[k]]
    return bool(field_scores and not bad_fields), bad_fields


def verify_users(domain, source_list):
    # TODO: An endpoint to verify a group of users does not seem to be
    #       available using Chenosis
    results = []
    for source in source_list:
        result = verify_user(domain, source)
        results.append(result)
    return results


def _get_requests(domain, config):
    """
    Returns a `Requests` instance for the Chenosis MTN KYC API
    """
    if config.provider == KycProviders.MTN_KYC:
        kyc_settings = settings.KYC_MTN_CONNECTION_SETTINGS
        connx, __ = ConnectionSettings.objects.get_or_create(
            domain=domain,
            name=CONNECTION_SETTINGS_NAME,
            defaults={
                'url': kyc_settings['url'],
                'auth_type': OAUTH2_CLIENT,
                'client_id': kyc_settings['client_id'],
                'client_secret': kyc_settings['client_secret'],
                'token_url': kyc_settings['token_url'],
            },
        )
    else:
        raise ValueError(f'KYC provider {config.provider!r} not supported')
    return connx.get_requests()


def get_user_data_for_api(source, config):
    """
        Returns a dictionary of user data for the API.
        ``source`` is a CommCareUser or a CommCareCase.
    """
    source_data = _get_source_data(source, config)
    user_data_for_api = {}
    for mapping in config.api_field_to_user_data_map:
        try:
            if mapping['source'] == 'standard':
                user_data_for_api[mapping['fieldName']] = getattr(source, mapping['mapsTo'])
            else:
                user_data_for_api[mapping['fieldName']] = source_data[mapping['mapsTo']]
        except (AttributeError, KeyError):
            # Conservative approach to skip the API field if data is not available for the user
            continue
    return user_data_for_api


def _get_source_data(source, config):
    """
        Returns a dictionary of source data.
        ``source`` is a CommCareUser or a CommCareCase.
    """
    if config.user_data_store == UserDataStore.CUSTOM_USER_DATA:
        source_data = source.get_user_data(config.domain)
    elif config.user_data_store == UserDataStore.USER_CASE:
        custom_user_case = source.get_usercase()
        if not custom_user_case:
            raise UserCaseNotFound("User case not found for the user.")
        source_data = custom_user_case.case_json
    else:
        source_data = source.case_json
    return source_data


def _validate_schema(endpoint, data):
    """
    Validate the data against the schema for the given endpoint
    """
    schema_filename = f'{_kebab_case(endpoint)}.json'
    schema_path = os.path.join(
        settings.BASE_DIR, 'corehq', 'apps', 'integration', 'kyc', 'schemas',
        schema_filename,
    )
    with open(schema_path) as f:
        schema = json.load(f)
    jsonschema.validate(data, schema)


def _kebab_case(value):
    """
    Convert a string to kebab-case

    >>> _kebab_case('Hello, World!')
    'hello-world'
    """
    value = camel_case_to_spaces(value)
    value = re.sub(r"[^\w\s-]", "-", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")
