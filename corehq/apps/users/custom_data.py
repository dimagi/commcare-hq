from __future__ import absolute_import
from corehq.apps.custom_data_fields.models import is_system_key
from corehq.apps.users.dbaccessors import get_all_commcare_users_by_domain
from corehq.apps.custom_data_fields.dbaccessors import get_by_domain_and_type


def remove_unused_custom_fields_from_users(domain):
    """
    Removes all unused custom data fields from all users in the domain
    """
    from corehq.apps.users.views.mobile.custom_data_fields import CUSTOM_USER_DATA_FIELD_TYPE
    fields_definition = get_by_domain_and_type(domain, CUSTOM_USER_DATA_FIELD_TYPE)
    assert fields_definition, 'remove_unused_custom_fields_from_users called without a valid CustomDataFieldsDefinition'
    configured_field_keys = set([f.slug for f in fields_definition.get_fields()])
    for user in get_all_commcare_users_by_domain(domain):
        keys_to_delete = _get_invalid_user_data_fields(user, configured_field_keys)
        if keys_to_delete:
            for key in keys_to_delete:
                del user.user_data[key]
            user.save()


def _get_invalid_user_data_fields(user, configured_field_keys):
    return [key for key in user.user_data if not is_system_key(key) and not key in configured_field_keys]
