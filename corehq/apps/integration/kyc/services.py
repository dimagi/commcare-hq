from corehq.apps.integration.kyc.models import UserDataStore


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
