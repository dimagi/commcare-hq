from corehq.apps.locations.models import SQLLocation
from dimagi.utils.logging import notify_exception


def is_submission_from_test_location(person_case):
    try:
        phi_location = SQLLocation.objects.get(location_id=person_case.owner_id)
    except SQLLocation.DoesNotExist:
        message = ("Location with id {location_id} not found. This is the owner for person with id: {person_id}"
                   .format(location_id=person_case.owner_id, person_id=person_case.case_id))
        notify_exception(None, message="[ENIKSHAY] {}".format(message))
        return True

    return phi_location.metadata.get('is_test', "yes") == "yes"
