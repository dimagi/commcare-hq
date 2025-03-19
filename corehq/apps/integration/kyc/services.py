import json
import os
import re
from collections import defaultdict

import requests

from django.conf import settings
from django.utils.text import camel_case_to_spaces

import jsonschema

from corehq.apps.integration.kyc.models import KycVerificationFailureCause, KycVerificationStatus
from corehq.util.metrics import metrics_counter


def verify_users(kyc_users, config):
    # TODO: An endpoint to verify a group of users does not seem to be
    #       available using Chenosis. If we have to do this with
    #       multiple calls, consider using Celery gevent workers.
    results = {}
    device_id = f'{__name__}.verify_users'
    errors_with_count = defaultdict(int)
    for kyc_user in kyc_users:
        verification_status = KycVerificationStatus.PENDING
        try:
            verification_status = verify_user(kyc_user, config)
            if verification_status == KycVerificationStatus.FAILED:
                errors_with_count[KycVerificationFailureCause.USER_INFORMATION_MISMATCH.value] += 1
        # TODO - Decide on how we want to handle these exceptions for the end user
        except jsonschema.exceptions.ValidationError:
            errors_with_count[KycVerificationFailureCause.USER_INFORMATION_INCOMPLETE.value] += 1
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            errors_with_count[KycVerificationFailureCause.NETWORK_ERROR.value] += 1
        except requests.HTTPError:
            errors_with_count[KycVerificationFailureCause.API_ERROR.value] += 1

        # Store result only when API successfully returns a verification response
        if verification_status in (KycVerificationStatus.PASSED, KycVerificationStatus.FAILED):
            kyc_user.update_verification_status(verification_status, device_id=device_id)

        results[kyc_user.user_id] = verification_status

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
    _validate_schema('kycVerify/v1', user_data)  # See kyc-verify-v1.json
    requests = config.get_connection_settings().get_requests()
    response = requests.post(
        f'/kycVerify/v1/customers/{user_data["phoneNumber"]}',
        json=user_data,
    )
    response.raise_for_status()
    field_scores = response.json().get('data', {})
    verification_successful = all(v >= required_thresholds[k] for k, v in field_scores.items())
    return KycVerificationStatus.PASSED if verification_successful else KycVerificationStatus.FAILED


def get_user_data_for_api(kyc_user, config):
    """
        Returns a dictionary of user data for the API.
        ``source`` is a CommCareUser or a CommCareCase.
    """
    return {
        api_field: kyc_user.get(user_data_property)
        for api_field, user_data_property in config.api_field_to_user_data_map.items()
        if kyc_user.get(user_data_property) is not None
    }


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
