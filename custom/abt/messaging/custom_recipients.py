from corehq.apps.users.models import CommCareUser


def abt_case_owner_location_parent(handler, reminder):
    case = reminder.case
    if not case:
        return None

    # Get the case owner, which we always expect to be a mobile worker in
    # this one-off feature
    owner = reminder.case_owner
    if not isinstance(owner, CommCareUser):
        return None

    # Get the case owner's location
    owner_location = owner.sql_location
    if not owner_location:
        return None

    # Get that location's parent location
    parent_location = owner_location.parent
    if not parent_location:
        return None

    return [parent_location]
