import json

from corehq.apps.integration.kyc.models import UserDataStore, KycConfig


class UserCaseNotFound(Exception):
    pass


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


def verify_customer_api(user_data_for_api, config):
    url = config.connection_settings.url
    requests = config.connection_settings.get
    headers = {'content-type': 'application/json'}
    response = requests.request('POST', url, data=json.dumps(user_data_for_api), headers=headers)
    response.raise_for_status()

    return response.json()


config = KycConfig.objects.get(pk=2)
requests = config.connection_settings.get_requests()
data = {
    "id": "0399948893822",
    "firstName": "Joe",
    "lastName": "Doe",
    "otherNames": "Den",
    "email": "example@example.com",
    "dateOfBirth": "1980-02-14",
    "gender": "M",
    "stateOfOrigin": "EK",
    "lgaOfOrigin": "EK20",
    "stateOfResidence": "LA",
    "lgaOfResidence": "LA02",
    "nationality": "Nigerian",
    "alternativePhoneNumber": "9062058602",
    "maritalStatus": "M",
}
response = requests.post(endpoint='customers/1?isConsentVerified=false', data=data)
print(response.status_code)
print(response.json())
