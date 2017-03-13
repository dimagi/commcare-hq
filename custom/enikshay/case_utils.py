import pytz
from collections import namedtuple
from django.utils.dateparse import parse_datetime

from corehq.apps.locations.models import SQLLocation

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.exceptions import (
    ENikshayCaseNotFound,
    NikshayCodeNotFound,
    NikshayLocationNotFound,
)
from corehq.form_processor.exceptions import CaseNotFound

CASE_TYPE_ADHERENCE = "adherence"
CASE_TYPE_OCCURRENCE = "occurrence"
CASE_TYPE_EPISODE = "episode"
CASE_TYPE_PERSON = "person"
CASE_TYPE_LAB_REFERRAL = "lab_referral"
CASE_TYPE_DRTB_HIV_REFERRAL = "drtb-hiv-referral"


def get_parent_of_case(domain, case_id, parent_case_type):
    case_accessor = CaseAccessors(domain)
    try:
        if not isinstance(case_id, basestring):
            case_id = case_id.case_id

        child_case = case_accessor.get_case(case_id)
    except CaseNotFound:
        raise ENikshayCaseNotFound(
            "Couldn't find case: {}".format(case_id)
        )

    parent_case_ids = [
        indexed_case.referenced_id for indexed_case in child_case.indices
    ]
    parent_cases = case_accessor.get_cases(parent_case_ids)
    open_parent_cases = [
        parent_case for parent_case in parent_cases
        if not parent_case.closed and parent_case.type == parent_case_type
    ]

    if not open_parent_cases:
        raise ENikshayCaseNotFound(
            "Couldn't find any open {} cases for id: {}".format(parent_case_type, case_id)
        )

    return open_parent_cases[0]


def get_occurrence_case_from_episode(domain, episode_case_id):
    """
    Gets the first open occurrence case for an episode
    """
    return get_parent_of_case(domain, episode_case_id, CASE_TYPE_OCCURRENCE)


def get_person_case_from_occurrence(domain, occurrence_case_id):
    """
    Gets the first open person case for an occurrence
    """
    return get_parent_of_case(domain, occurrence_case_id, CASE_TYPE_PERSON)


def get_occurrence_case_from_test(domain, test_case_id):
    """
        Gets the first open occurrence case for a test
        """
    return get_parent_of_case(domain, test_case_id, CASE_TYPE_OCCURRENCE)


def get_person_case_from_episode(domain, episode_case_id):
    return get_person_case_from_occurrence(
        domain,
        get_occurrence_case_from_episode(domain, episode_case_id).case_id
    )


def get_open_occurrence_case_from_person(domain, person_case_id):
    """
    Gets the first open 'occurrence' case for the person

    Assumes the following case structure:
    Person <--ext-- Occurrence

    """
    case_accessor = CaseAccessors(domain)
    occurrence_cases = case_accessor.get_reverse_indexed_cases([person_case_id])
    open_occurrence_cases = [case for case in occurrence_cases
                             if not case.closed and case.type == CASE_TYPE_OCCURRENCE]
    if not open_occurrence_cases:
        raise ENikshayCaseNotFound(
            "Person with id: {} exists but has no open occurrence cases".format(person_case_id)
        )
    return open_occurrence_cases[0]


def get_open_episode_case_from_occurrence(domain, occurrence_case_id):
    """
    Gets the first open 'episode' case for the occurrence

    Assumes the following case structure:
    Occurrence <--ext-- Episode

    """
    case_accessor = CaseAccessors(domain)
    episode_cases = case_accessor.get_reverse_indexed_cases([occurrence_case_id])
    open_episode_cases = [case for case in episode_cases
                          if not case.closed and case.type == CASE_TYPE_EPISODE and
                          case.dynamic_case_properties().get('episode_type') == "confirmed_tb"]
    if open_episode_cases:
        return open_episode_cases[0]
    else:
        raise ENikshayCaseNotFound(
            "Occurrence with id: {} exists but has no open episode cases".format(occurrence_case_id)
        )


def get_lab_referral_from_test(domain, test_case_id):
    """
    Gets the first 'lab_referral' case for the test

    Assumes the following case structure:
    LabReferral <--ext-- test

    """
    case_accessor = CaseAccessors(domain)
    reverse_indexed_cases = case_accessor.get_reverse_indexed_cases([test_case_id])
    lab_referral_cases = [case for case in reverse_indexed_cases if case.type == CASE_TYPE_LAB_REFERRAL]
    if lab_referral_cases:
        return lab_referral_cases[0]
    else:
        raise ENikshayCaseNotFound(
            "test with id: {} exists but has no lab referral cases".format(test_case_id)
        )


def get_open_drtb_hiv_case_from_episode(domain, episode_case_id):
    """
    Gets the first open 'drtb-hiv-referral' case for the episode

    Assumes the following case structure:
    episode <--ext-- drtb-hiv-referral
    """
    case_accessor = CaseAccessors(domain)
    open_drtb_cases = [
        case for case in case_accessor.get_reverse_indexed_cases([episode_case_id])
        if not case.closed and case.type == CASE_TYPE_DRTB_HIV_REFERRAL
    ]
    if open_drtb_cases:
        return open_drtb_cases[0]
    else:
        raise ENikshayCaseNotFound(
            "Occurrence with id: {} exists but has no open episode cases".format(episode_case_id)
        )


def get_open_episode_case_from_person(domain, person_case_id):
    """
    Gets the first open 'episode' case for the person

    Assumes the following case structure:
    Person <--ext-- Occurrence <--ext-- Episode

    """
    return get_open_episode_case_from_occurrence(
        domain, get_open_occurrence_case_from_person(domain, person_case_id).case_id
    )


def get_episode_case_from_adherence(domain, adherence_case_id):
    """Gets the 'episode' case associated with an adherence datapoint

    Assumes the following case structure:
    Episode <--ext-- Adherence
    """
    return get_parent_of_case(domain, adherence_case_id, CASE_TYPE_EPISODE)


def get_adherence_cases_between_dates(domain, person_case_id, start_date, end_date):
    case_accessor = CaseAccessors(domain)
    episode = get_open_episode_case_from_person(domain, person_case_id)
    indexed_cases = case_accessor.get_reverse_indexed_cases([episode.case_id])
    open_pertinent_adherence_cases = [
        case for case in indexed_cases
        if not case.closed and case.type == CASE_TYPE_ADHERENCE and
        (start_date.astimezone(pytz.UTC) <=
         parse_datetime(case.dynamic_case_properties().get('adherence_date')).astimezone(pytz.UTC) <=
         end_date.astimezone(pytz.UTC))
    ]

    return open_pertinent_adherence_cases


def update_case(domain, case_id, updated_properties, external_id=None):
    kwargs = {
        'case_id': case_id,
        'update': updated_properties,
    }
    if external_id is not None:
        kwargs.update({'external_id': external_id})

    post_case_blocks(
        [CaseBlock(**kwargs).as_xml()],
        {'domain': domain}
    )


def get_person_locations(person_case):
    PersonLocationHierarchy = namedtuple('PersonLocationHierarchy', 'sto dto tu phi')
    try:
        phi_location = SQLLocation.objects.get(location_id=person_case.owner_id)
    except SQLLocation.DoesNotExist:
        raise NikshayLocationNotFound(
            "Location with id {location_id} not found. This is the owner for person with id: {person_id}"
            .format(location_id=person_case.owner_id, person_id=person_case.case_id)
        )

    try:
        tu_location = phi_location.parent
        district_location = tu_location.parent
        city_location = district_location.parent
        state_location = city_location.parent
    except AttributeError:
        raise NikshayLocationNotFound("Location structure error for person: {}".format(person_case.case_id))
    try:
        # TODO: verify how location codes will be stored
        return PersonLocationHierarchy(
            sto=state_location.metadata['nikshay_code'],
            dto=district_location.metadata['nikshay_code'],
            tu=tu_location.metadata['nikshay_code'],
            phi=phi_location.metadata['nikshay_code'],
        )
    except (KeyError, AttributeError) as e:
        raise NikshayCodeNotFound("Nikshay codes not found: {}".format(e))
