from corehq.apps.locations.models import SQLLocation


def host_case_owner_location(handler, reminder):
    case = reminder.case
    if not case:
        return None

    host = case.host
    if not host:
        return None

    location_id = host.owner_id
    if not location_id:
        return None

    location = SQLLocation.by_location_id(location_id)
    if not location or location.is_archived or location.domain != reminder.domain:
        return None

    return [location]


def host_case_owner_location_parent(handler, reminder):
    location = host_case_owner_location(handler, reminder)
    if not location:
        return None

    return [location[0].parent]
