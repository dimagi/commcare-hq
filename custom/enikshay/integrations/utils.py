from corehq.apps.locations.models import SQLLocation
from custom.enikshay.exceptions import NikshayLocationNotFound, ENikshayCaseNotFound
from custom.enikshay.case_utils import get_person_case_from_episode


def _is_submission_from_test_location(person_case):
    try:
        phi_location = SQLLocation.objects.get(location_id=person_case.owner_id)
    except SQLLocation.DoesNotExist:
        raise NikshayLocationNotFound(
            "Location with id {location_id} not found. This is the owner for person with id: {person_id}"
            .format(location_id=person_case.owner_id, person_id=person_case.case_id)
        )
    return phi_location.metadata.get('is_test', "yes") == "yes"


def is_valid_person_submission(person_case):
    return not _is_submission_from_test_location(person_case)


def is_valid_episode_submission(episode_case):
    try:
        person_case = get_person_case_from_episode(episode_case.domain, episode_case)
    except ENikshayCaseNotFound:
        return False
    return not _is_submission_from_test_location(person_case)
