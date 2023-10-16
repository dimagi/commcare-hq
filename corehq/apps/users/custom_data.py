from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.users.dbaccessors import get_all_commcare_users_by_domain


def remove_unused_custom_fields_from_users(domain):
    """
    Removes all unused custom data fields from all users in the domain
    """
    from corehq.apps.users.views.mobile.custom_data_fields import CUSTOM_USER_DATA_FIELD_TYPE
    fields_definition = CustomDataFieldsDefinition.get(domain, CUSTOM_USER_DATA_FIELD_TYPE)
    assert fields_definition, 'remove_unused_custom_fields_from_users called without a valid definition'
    schema_fields = {f.slug for f in fields_definition.get_fields()}
    for user in get_all_commcare_users_by_domain(domain):
        user_data = user.get_user_data(domain)
        changed = user_data.remove_unrecognized(schema_fields)
        if changed:
            user.save()
