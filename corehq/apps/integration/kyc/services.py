import json
import os
import re
from collections import defaultdict
from pyphonetics.distance_metrics import levenshtein_distance

from django.conf import settings
from django.utils.text import camel_case_to_spaces

import jsonschema
import requests

from corehq.apps.integration.kyc.models import (
    KycVerificationFailureCause,
    KycVerificationStatus,
)
from corehq.util.metrics import metrics_counter


def verify_users(kyc_users, config, verified_by):
    # TODO: An endpoint to verify a group of users does not seem to be
    #       available using Chenosis. If we have to do this with
    #       multiple calls, consider using Celery gevent workers.
    results = {}
    device_id = f'{__name__}.verify_users'
    errors_with_count = defaultdict(int)
    for kyc_user in kyc_users:
        verification_status, verification_error = verify_user(kyc_user, config)

        if verification_error:
            errors_with_count[verification_error] += 1

        kyc_user.update_verification_status(
            verification_status,
            verified_by,
            device_id=device_id,
            error_message=verification_error,
        )
        results[kyc_user.user_id] = verification_status

    _report_verification_failure_metric(config.domain, errors_with_count)
    return results


def verify_user(kyc_user, config):
    verification_error = None

    try:
        verify_method = config.get_kyc_api_method()
        verification_status = verify_method(kyc_user, config)
        if verification_status == KycVerificationStatus.FAILED:
            verification_error = KycVerificationFailureCause.USER_INFORMATION_MISMATCH.value

    except jsonschema.exceptions.ValidationError:
        verification_error = KycVerificationFailureCause.USER_INFORMATION_INCOMPLETE.value
        verification_status = KycVerificationStatus.ERROR

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        verification_error = KycVerificationFailureCause.NETWORK_ERROR.value
        verification_status = KycVerificationStatus.ERROR

    except requests.HTTPError:
        verification_error = KycVerificationFailureCause.API_ERROR.value
        verification_status = KycVerificationStatus.ERROR

    return verification_status, verification_error


def mtn_kyc_verify(kyc_user, config):
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

    user_data = get_user_data_for_api(kyc_user, config)
    _validate_schema('kycVerify/v1', user_data)  # See kyc-verify-v1.json
    requests = config.connection_settings.get_requests()
    response = requests.post(
        f'/kycVerify/v1/customers/{user_data["phoneNumber"]}',
        json=user_data,
    )
    response.raise_for_status()
    field_scores = response.json().get('data', {})
    verification_successful = all(v >= config.passing_threshold[k] for k, v in field_scores.items())
    return KycVerificationStatus.PASSED if verification_successful else KycVerificationStatus.FAILED


def orange_cameroon_kyc_verify(kyc_user, config):
    """
    Verify a user using the Orange Cameroon KYC API.

    Returns True if all user data is accurate above its required
    threshold, otherwise False.
    """

    # Documentation:  https://apiis.orange.cm/store/
    # Example request:
    #
    #     POST https://api-s1.orange.cm/omcoreapis/1.0.2/infos/subscriber/customer/{customerMsisdn}
    #     {
    #       "pin": "test",
    #       "channelMsisdn": "123456789"
    #     }
    #
    # Example 200 response:
    #
    #    {
    #     "message": "customer 8877665544 successfully retrieve full name.",
    #     "data": {
    #         "firstName": "First",
    #         "lastName": "Last"
    #     }
    # }

    user_data = get_user_data_for_api(kyc_user, config)
    _validate_name_fields(config, user_data)
    requests = config.connection_settings.get_requests()
    response = requests.post(
        f'/omcoreapis/1.0.2/infos/subscriber/customer/{user_data["phoneNumber"]}',
        json={
            "pin": settings.ORANGE_CAMEROON_API_CREDS['channel_pin'],
            "channelMsisdn": settings.ORANGE_CAMEROON_API_CREDS['channel_msisdn'],
        },
        headers={
            'X-AUTH-TOKEN': settings.ORANGE_CAMEROON_API_CREDS['x-auth-token'],
        }
    )
    response.raise_for_status()
    api_data = response.json().get('data', {})
    if config.stores_full_name:
        api_full_name = f"{api_data['firstName']} {api_data['lastName']}".strip()
        user_full_name = user_data['fullName'].strip()
        score = order_and_case_insensitive_matching_score(api_full_name, user_full_name)
        if score < config.passing_threshold['fullName']:
            return KycVerificationStatus.FAILED
    else:
        for field, threshold_value in config.passing_threshold.items():
            # lastName is optional in user data, but if API returns it and user doesn't have it, fail
            if field == 'lastName' and field not in user_data:
                if field in api_data and api_data[field].strip():
                    # API has lastName but user doesn't - this is a mismatch
                    return KycVerificationStatus.FAILED
                # Both don't have lastName - skip validation
                continue
            api_value = api_data.get(field, '').strip().lower()
            user_value = user_data[field].strip().lower()
            score = get_percent_matching_score(api_value, user_value)
            if score < threshold_value:
                return KycVerificationStatus.FAILED

    return KycVerificationStatus.PASSED


def _validate_name_fields(config, user_data):
    if config.stores_full_name:
        field = 'fullName'
    else:
        # User may not have last name, but first name is required
        field = 'firstName'
    value = user_data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise jsonschema.exceptions.ValidationError(f'{field} is required')


def _report_verification_failure_metric(domain, errors_with_count):
    for error, count in errors_with_count.items():
        metrics_counter(
            'commcare.integration.kyc.verification_failure.count',
            count,
            tags={'domain': domain, 'error': error}
        )


def get_user_data_for_api(kyc_user, config):
    """
        Returns a dictionary of user data for the API.
        ``source`` is a CommCareUser or a CommCareCase.
    """
    return {
        api_field: kyc_user.get(user_data_property)
        for api_field, user_data_property in config.get_api_field_to_user_data_map_values().items()
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


def order_and_case_insensitive_matching_score(value1, value2):
    """Case insensitive and order insensitive percent matching score between two strings
    based on Levenshtein distance.
    This is useful for comparing full names where the order of first and last names may vary,
    which commonly occurs in HQ projects.

    >>> order_and_case_insensitive_matching_score("Jeanne d'Arc", "D'ARC Jeanne")
    100.0
    >>> order_and_case_insensitive_matching_score("D'ARC Jeanne", "Jehanne Darc")
    83.33333333333334
    """
    if value1 is None or value2 is None:
        raise ValueError('Both values are required')

    if value1 == '' and value2 == '':
        return 100.0

    parts1 = sorted(value1.lower().split())
    parts2 = sorted(value2.lower().split())
    return get_percent_matching_score(" ".join(parts1), " ".join(parts2))


def get_percent_matching_score(value1, value2):
    """Case sensitive percent matching score between two strings based on Levenshtein distance.

    >>> get_percent_matching_score("Jessica", "Jessica")
    100.0
    >>> get_percent_matching_score("Jessica", "jessica")
    85.71428571428572
    >>> get_percent_matching_score("Jessica", "Jessika")
    85.71428571428572
    """
    if value1 is None or value2 is None:
        raise ValueError('Both values are required')

    if value1 == '' and value2 == '':
        return 100.0

    dist = levenshtein_distance(value1, value2)
    max_len = max(len(value1), len(value2))
    return (1.0 - dist / max_len) * 100
