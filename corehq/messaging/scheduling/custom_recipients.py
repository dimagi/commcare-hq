from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.exceptions import CaseNotFound
from couchdbkit.exceptions import ResourceNotFound


def host_case_owner_location_from_case(domain, case):
    if not case:
        return None

    try:
        host = case.host
    except (CaseNotFound, ResourceNotFound):
        return None

    if not host:
        return None

    location_id = host.owner_id
    if not location_id:
        return None

    location = SQLLocation.by_location_id(location_id)
    if not location or location.is_archived or location.domain != domain:
        return None

    return location


def host_case_owner_location_parent_from_case(domain, case):
    result = host_case_owner_location_from_case(domain, case)
    if not result:
        return None

    parent_location = result.parent
    if not parent_location:
        return None

    return parent_location


def host_case_owner_location(case_schedule_instance):
    return host_case_owner_location_from_case(case_schedule_instance.domain, case_schedule_instance.case)


def host_case_owner_location_parent(case_schedule_instance):
    return host_case_owner_location_parent_from_case(case_schedule_instance.domain, case_schedule_instance.case)
