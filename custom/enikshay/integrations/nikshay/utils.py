from __future__ import absolute_import

from corehq.apps.locations.dbaccessors import get_all_users_by_location
from custom.enikshay.integrations.nikshay.exceptions import NikshayHealthEstablishmentInvalidUpdate


def get_location_user_for_notification(location):
    all_users_assigned_to_location = get_all_users_by_location(
        location.domain,
        location.location_id
    )
    location_type_code = location.location_type.code
    user_with_user_type_as_loc = []
    for user in all_users_assigned_to_location:
        if user.user_data.get('usertype') == location_type_code:
            user_with_user_type_as_loc.append(user)
    if len(user_with_user_type_as_loc) == 0:
        raise NikshayHealthEstablishmentInvalidUpdate("Location user not found")
    if len(user_with_user_type_as_loc) > 1:
        raise NikshayHealthEstablishmentInvalidUpdate("Multiple location users found")
    return user_with_user_type_as_loc[0]
