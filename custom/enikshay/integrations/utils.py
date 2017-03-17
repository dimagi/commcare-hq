from corehq.apps.locations.models import SQLLocation
from custom.enikshay.exceptions import NikshayLocationNotFound


def is_submission_from_test_location(person_case):
    try:
        phi_location = SQLLocation.objects.get(location_id=person_case.owner_id)
    except SQLLocation.DoesNotExist:
        raise NikshayLocationNotFound(
            "Location with id {location_id} not found. This is the owner for person with id: {person_id}"
            .format(location_id=person_case.owner_id, person_id=person_case.case_id)
        )
    return phi_location.metadata.get('is_test', "yes") == "yes"
