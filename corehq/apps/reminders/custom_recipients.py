from couchdbkit.exceptions import ResourceNotFound

from corehq.form_processor.exceptions import CaseNotFound
from corehq.messaging.scheduling.custom_recipients import (
    host_case_owner_location_from_case,
    host_case_owner_location_parent_from_case,
)


def host_case_owner_location(handler, reminder):
    try:
        case = reminder.case
    except (CaseNotFound, ResourceNotFound):
        return None

    result = host_case_owner_location_from_case(reminder.domain, case)
    if result:
        return [result]

    return None


def host_case_owner_location_parent(handler, reminder):
    try:
        case = reminder.case
    except (CaseNotFound, ResourceNotFound):
        return None

    result = host_case_owner_location_parent_from_case(reminder.domain, case)
    if result:
        return [result]

    return None
