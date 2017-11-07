from __future__ import absolute_import
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.exceptions import CaseNotFound
from couchdbkit.exceptions import ResourceNotFound


def host_case_owner_location(handler, reminder):
    try:
        case = reminder.case
    except (CaseNotFound, ResourceNotFound):
        return None

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
    if not location or location.is_archived or location.domain != reminder.domain:
        return None

    return [location]


def host_case_owner_location_parent(handler, reminder):
    result = host_case_owner_location(handler, reminder)
    if not result:
        return None

    parent_location = result[0].parent
    if not parent_location:
        return None

    return [parent_location]
