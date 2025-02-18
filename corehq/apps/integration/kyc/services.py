import json
import os
import re
from datetime import datetime

from django.conf import settings
from django.utils.text import camel_case_to_spaces

import jsonschema

from corehq.apps.hqcase.utils import update_case
from corehq.apps.integration.kyc.models import UserDataStore
from corehq.apps.users.models import CommCareUser


class UserCaseNotFound(Exception):
    pass


def verify_users(user_objs, config):
    # TODO: An endpoint to verify a group of users does not seem to be
    #       available using Chenosis. If we have to do this with
    #       multiple calls, consider using Celery gevent workers.
    results = []
    for user_obj in user_objs:
        is_verified = verify_user(user_obj, config)
        save_result(user_obj, config, is_verified)
        results.append(is_verified)
    return results


def verify_user(user_obj, config):
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

    user_data = get_user_data_for_api(user_obj, config)
    _validate_schema('kycVerify/v1', user_data)
    requests = config.get_connection_settings().get_requests()
    response = requests.post(
        f'/kycVerify/v1/customers/{user_data["phoneNumber"]}',
        json=user_data,
    )
    response.raise_for_status()
    field_scores = response.json().get('data', {})
    return all(v >= required_thresholds[k] for k, v in field_scores.items())


def save_result(user_obj, config, is_verified):
    update = {
        'kyc_provider': config.provider.value,  # TODO: Or config.provider.label?
        'kyc_last_verified_at': datetime.utcnow(),  # TODO: UTC or project timezone?
        'kyc_is_verified': is_verified,
    }
    if config.user_data_store == UserDataStore.CUSTOM_USER_DATA:
        user_data = user_obj.get_user_data(config.domain)
        user_data.update(update)
    elif config.user_data_store == UserDataStore.USER_CASE:
        case = user_obj.get_usercase()
        update_case(
            config.domain,
            case.case_id,
            case_properties=update,
            device_id='corehq.apps.integration.kyc.services.save_result',
        )
    else:  # UserDataStore.OTHER_CASE_TYPE
        update_case(
            config.domain,
            user_obj.case_id,
            case_properties=update,
            device_id='corehq.apps.integration.kyc.services.save_result',
        )


def get_user_data_for_api(source, config):
    """
        Returns a dictionary of user data for the API.
        ``source`` is a CommCareUser or a CommCareCase.
    """
    # CommCareUser properties that could map to API fields
    safe_commcare_user_properties = {
        'first_name',
        'last_name',
        'full_name',
        'name',
        'email',
        'username',  # For CommCareUsers this is an email address
        'phone_number',
        'default_phone_number',
    }
    source_data = _get_source_data(source, config)
    user_data_for_api = {}
    for mapping in config.api_field_to_user_data_map:
        if mapping['mapsTo'] in source_data:
            # Fetch value from usercase / custom user data by default
            value = source_data[mapping['mapsTo']]
        elif (
            isinstance(source, CommCareUser)
            and mapping['mapsTo'] in safe_commcare_user_properties
        ):
            # Fall back to CommCareUser
            value = getattr(source, mapping['mapsTo'])
        else:
            # Conservative approach to skip the API field if data is not available for the user
            continue
        user_data_for_api[mapping['fieldName']] = value
    return user_data_for_api


def _get_source_data(source, config):
    """
    Returns a dictionary of source data.

    :param source: A CommCareUser or a CommCareCase.
    :param config: A KycConfig instance.
    """
    if config.user_data_store == UserDataStore.CUSTOM_USER_DATA:
        source_data = source.get_user_data(config.domain).to_dict()
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
