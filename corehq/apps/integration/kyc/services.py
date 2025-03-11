import json
import os
import re
from collections import defaultdict

import requests

from django.conf import settings
from django.utils.text import camel_case_to_spaces

import jsonschema

from corehq.apps.integration.kyc.models import KycVerificationFailureCause
from corehq.util.metrics import metrics_counter


def verify_users(kyc_users, config):
    # TODO: An endpoint to verify a group of users does not seem to be
    #       available using Chenosis. If we have to do this with
    #       multiple calls, consider using Celery gevent workers.
    results = {}
    device_id = f'{__name__}.verify_users'
    errors_with_count = defaultdict(int)
    for kyc_user in kyc_users:
        verification_error = None
        is_verified = False
        try:
            is_verified = verify_user(kyc_user, config)
            if not is_verified:
                verification_error = KycVerificationFailureCause.USER_INFORMATION_MISMATCH.value
                errors_with_count[verification_error] += 1
        except jsonschema.exceptions.ValidationError:
            verification_error = KycVerificationFailureCause.USER_INFORMATION_INCOMPLETE.value
            errors_with_count[verification_error] += 1
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            verification_error = KycVerificationFailureCause.NETWORK_ERROR.value
            errors_with_count[verification_error] += 1
        except requests.HTTPError:
            verification_error = KycVerificationFailureCause.API_ERROR.value
            errors_with_count[verification_error] += 1

        kyc_user.update_verification_status(is_verified, device_id=device_id, error_message=verification_error)
        results[kyc_user.user_id] = is_verified

    _report_verification_failure_metric(config.domain, errors_with_count)
    return results


def _report_verification_failure_metric(domain, errors_with_count):
    for error, count in errors_with_count.items():
        metrics_counter(
            'commcare.integration.kyc.verification_failure.count',
            count,
            tags={'domain': domain, 'error': error}
        )


def verify_user(kyc_user, config):
    """
    Verify a user using the Chenosis MTN KYC API.

    Returns True if all user data is accurate above its required
    threshold, otherwise False.
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
    required_thresholds = {
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

    user_data = get_user_data_for_api(kyc_user, config)
    _validate_schema('kycVerify/v1', user_data)
    requests = config.get_connection_settings().get_requests()
    response = requests.post(
        f'/kycVerify/v1/customers/{user_data["phoneNumber"]}',
        json=user_data,
    )
    response.raise_for_status()
    field_scores = response.json().get('data', {})
    return all(v >= required_thresholds[k] for k, v in field_scores.items())


def get_user_data_for_api(kyc_user, config):
    """
        Returns a dictionary of user data for the API.
        ``source`` is a CommCareUser or a CommCareCase.
    """
    user_data_for_api = {}
    for api_field, user_data_property in config.api_field_to_user_data_map.items():
        try:
            value = kyc_user[user_data_property]
        except KeyError:
            # Conservative approach to skip the API field if data is not available for the user
            continue
        user_data_for_api[api_field] = value
    return user_data_for_api


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
