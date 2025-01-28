from corehq.apps.integration.kyc.models import UserDataStore
from corehq.form_processor.models import CommCareCase


class CustomUserDataNotFound(Exception):
    pass


def get_user_data_for_api(user, config):
    custom_user_data = _get_custom_user_data(user, config)
    user_data_for_api = {}
    for mapping in config.api_field_to_user_data_map:
        try:
            if mapping['source'] == 'standard':
                user_data_for_api[mapping['fieldName']] = getattr(user, mapping['mapsTo'])
            else:
                user_data_for_api[mapping['fieldName']] = custom_user_data[mapping['mapsTo']]
        except (AttributeError, KeyError):
            # Conservative approach to skip the API field if data is not available for the user
            continue
    return user_data_for_api


def _get_custom_user_data(user, config):
    if config.user_data_store == UserDataStore.CUSTOM_USER_DATA:
        return user.get_user_data(config.domain)

    if config.user_data_store == UserDataStore.USER_CASE:
        custom_user_case = user.get_usercase()
    else:
        custom_user_case = CommCareCase.objects.get_case_by_external_id(
            config.domain,
            user.user_id,
            config.other_case_type,
        )
    if not custom_user_case:
        raise CustomUserDataNotFound("Custom user data not found for the user.")
    custom_user_data = custom_user_case.case_json
    return custom_user_data
