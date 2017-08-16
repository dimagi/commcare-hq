import pytz
from collections import namedtuple, defaultdict
from django.utils.dateparse import parse_datetime
from dateutil.parser import parse

from corehq.apps.locations.models import SQLLocation
from corehq.util.decorators import hqnottest
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.exceptions import (
    ENikshayCaseNotFound,
    NikshayCodeNotFound,
    NikshayLocationNotFound,
    ENikshayException)
from corehq.form_processor.exceptions import CaseNotFound

CASE_TYPE_ADHERENCE = "adherence"
CASE_TYPE_OCCURRENCE = "occurrence"
CASE_TYPE_EPISODE = "episode"
CASE_TYPE_PERSON = "person"
CASE_TYPE_REFERRAL = "referral"
CASE_TYPE_TRAIL = "trail"
CASE_TYPE_LAB_REFERRAL = "lab_referral"
CASE_TYPE_DRTB_HIV_REFERRAL = "drtb-hiv-referral"
CASE_TYPE_TEST = "test"
CASE_TYPE_PRESCRIPTION = "prescription"
CASE_TYPE_VOUCHER = "voucher"
CASE_TYPE_PRESCRIPTION = "prescription"
CASE_TYPE_DRUG_RESISTANCE = "drug_resistance"
CASE_TYPE_SECONDARY_OWNER = "secondary_owner"


def get_all_parents_of_case(domain, case_id):
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

    return parent_cases


def get_parent_of_case(domain, case_id, parent_case_type):
    parent_cases = get_all_parents_of_case(domain, case_id)
    case_type_open_parent_cases = [
        parent_case for parent_case in parent_cases
        if not parent_case.closed and parent_case.type == parent_case_type
    ]

    if not case_type_open_parent_cases:
        raise ENikshayCaseNotFound(
            "Couldn't find any open {} cases for id: {}".format(parent_case_type, case_id)
        )

    return case_type_open_parent_cases[0]


def get_first_parent_of_case(domain, case_id, parent_case_type):
    parent_cases = get_all_parents_of_case(domain, case_id)
    case_type_parent_cases = [
        parent_case for parent_case in parent_cases if parent_case.type == parent_case_type
    ]

    if not case_type_parent_cases:
        raise ENikshayCaseNotFound(
            "Couldn't find any {} cases for id: {}".format(parent_case_type, case_id)
        )

    return case_type_parent_cases[0]


def get_occurrence_case_from_episode(domain, episode_case_id):
    """
    Gets the first occurrence case for an episode
    """
    return get_first_parent_of_case(domain, episode_case_id, CASE_TYPE_OCCURRENCE)


def get_person_case_from_occurrence(domain, occurrence_case_id):
    """
    Gets the first person case for an occurrence
    """
    return get_first_parent_of_case(domain, occurrence_case_id, CASE_TYPE_PERSON)


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


def get_open_referral_case_from_person(domain, person_case_id):
    case_accessor = CaseAccessors(domain)
    reverse_indexed_cases = case_accessor.get_reverse_indexed_cases([person_case_id])
    open_referral_cases = [
        case for case in reverse_indexed_cases
        if not case.closed and case.type == CASE_TYPE_REFERRAL
    ]
    occurrence_cases = [
        case.case_id for case in reverse_indexed_cases
        if not case.closed and case.type == CASE_TYPE_OCCURRENCE
    ]
    reversed_indexed_occurrence = case_accessor.get_reverse_indexed_cases(occurrence_cases)
    open_referral_cases.extend(
        case for case in reversed_indexed_occurrence
        if not case.closed and case.type == CASE_TYPE_REFERRAL
    )
    if not open_referral_cases:
        return None
    if len(open_referral_cases) == 1:
        return open_referral_cases[0]
    else:
        raise ENikshayException(
            "Expected none or one open referral case for person with id: {}".format(person_case_id)
        )


def get_latest_trail_case_from_person(domain, person_case_id):
    case_accessor = CaseAccessors(domain)
    reverse_indexed_cases = case_accessor.get_reverse_indexed_cases([person_case_id])
    trail_cases = [
        case for case in reverse_indexed_cases
        if case.type == CASE_TYPE_TRAIL
    ]

    # Also check for trails on the occurrence
    occurrence_case_ids = [
        case.case_id for case in reverse_indexed_cases
        if case.type == CASE_TYPE_OCCURRENCE and not case.closed
    ]
    reverse_indexed_occurrence = case_accessor.get_reverse_indexed_cases(occurrence_case_ids)
    trail_cases.extend([case for case in reverse_indexed_occurrence if case.type == CASE_TYPE_TRAIL])

    trails_with_server_opened_on = []
    for trail in trail_cases:
        server_opened_on = trail.actions[0].server_date
        trails_with_server_opened_on.append((server_opened_on, trail))

    trails_with_server_opened_on.sort()
    if trails_with_server_opened_on:
        # Return the latest trail case
        return trails_with_server_opened_on[-1][1]
    else:
        return None


def get_episode_case_from_adherence(domain, adherence_case_id):
    """Gets the 'episode' case associated with an adherence datapoint

    Assumes the following case structure:
    Episode <--ext-- Adherence
    """
    return get_parent_of_case(domain, adherence_case_id, CASE_TYPE_EPISODE)


@hqnottest
def get_occurrence_case_from_test(domain, test_case_id):
    """
        Gets the first open occurrence case for a test
        """
    return get_parent_of_case(domain, test_case_id, CASE_TYPE_OCCURRENCE)


@hqnottest
def get_private_diagnostic_test_cases_from_episode(domain, episode_case_id):
    """Returns all test cases for a particular episode
    """
    occurrence_case = get_occurrence_case_from_episode(domain, episode_case_id)
    case_accessor = CaseAccessors(domain)
    indexed_cases = case_accessor.get_reverse_indexed_cases([occurrence_case.case_id])
    open_test_cases = [
        case for case in indexed_cases
        if not case.closed
        and case.type == CASE_TYPE_TEST
        and case.get_case_property('purpose_of_test') == 'diagnostic'
        and case.get_case_property('date_reported') is not None
        and case.get_case_property('date_reported') != ''
        and case.get_case_property('enrolled_in_private') == 'true'
    ]
    return sorted(open_test_cases, key=lambda c: c.get_case_property('date_reported'))


def get_adherence_cases_between_dates(domain, person_case_id, start_date, end_date):
    episode = get_open_episode_case_from_person(domain, person_case_id)
    case_accessor = CaseAccessors(domain)
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
    """
    public locations hierarchy
    sto -> cto -> dto -> tu -> phi

    private locations hierarchy
    sto-> cto -> dto -> pcp
    """
    if person_case.dynamic_case_properties().get(ENROLLED_IN_PRIVATE) == 'true':
        return _get_private_locations(person_case)
    else:
        return _get_public_locations(person_case)


def _get_public_locations(person_case):
    PublicPersonLocationHierarchy = namedtuple('PersonLocationHierarchy', 'sto dto tu phi')
    try:
        phi_location = SQLLocation.active_objects.get(domain=person_case.domain, location_id=person_case.owner_id)
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
        return PublicPersonLocationHierarchy(
            sto=state_location.metadata['nikshay_code'],
            dto=district_location.metadata['nikshay_code'],
            tu=tu_location.metadata['nikshay_code'],
            phi=phi_location.metadata['nikshay_code'],
        )
    except (KeyError, AttributeError) as e:
        raise NikshayCodeNotFound("Nikshay codes not found: {}".format(e))


def _get_private_locations(person_case):
    PrivatePersonLocationHierarchy = namedtuple('PersonLocationHierarchy', 'sto dto pcp tu')
    try:
        pcp_location = SQLLocation.active_objects.get(domain=person_case.domain, location_id=person_case.owner_id)
    except SQLLocation.DoesNotExist:
        raise NikshayLocationNotFound(
            "Location with id {location_id} not found. This is the owner for person with id: {person_id}"
            .format(location_id=person_case.owner_id, person_id=person_case.case_id)
        )

    try:
        tu_location_nikshay_code = pcp_location.metadata['nikshay_tu_id'] or None
    except KeyError:
        tu_location_nikshay_code = None

    try:
        district_location = pcp_location.parent
        city_location = district_location.parent
        state_location = city_location.parent
    except AttributeError:
        raise NikshayLocationNotFound("Location structure error for person: {}".format(person_case.case_id))
    try:
        return PrivatePersonLocationHierarchy(
            sto=state_location.metadata['nikshay_code'],
            dto=district_location.metadata['nikshay_code'],
            pcp=pcp_location.metadata['nikshay_code'],
            tu=tu_location_nikshay_code
        )
    except (KeyError, AttributeError) as e:
        raise NikshayCodeNotFound("Nikshay codes not found: {}".format(e))


@hqnottest
def get_lab_referral_from_test(domain, test_case_id):
    case_accessor = CaseAccessors(domain)
    reverse_indexed_cases = case_accessor.get_reverse_indexed_cases([test_case_id])
    lab_referral_cases = [case for case in reverse_indexed_cases if case.type == CASE_TYPE_LAB_REFERRAL]
    if lab_referral_cases:
        return lab_referral_cases[0]
    else:
        raise ENikshayCaseNotFound(
            "test with id: {} exists but has no lab referral cases".format(test_case_id)
        )


def get_adherence_cases_by_day(domain, episode_case_id):
    indexed_cases = CaseAccessors(domain).get_reverse_indexed_cases([episode_case_id])
    adherence_cases = [
        case for case in indexed_cases
        if case.type == CASE_TYPE_ADHERENCE
    ]

    adherence = defaultdict(list)  # datetime.date -> list of adherence cases

    for case in adherence_cases:
        # adherence_date is in India timezone
        adherence_datetime = parse(case.dynamic_case_properties().get('adherence_date'))
        adherence[adherence_datetime.date()].append(case)

    return adherence


def get_person_case(domain, case_id):
    try:
        case = CaseAccessors(domain).get_case(case_id)
    except CaseNotFound:
        raise ENikshayCaseNotFound("Couldn't find case: {}".format(case_id))

    case_type = case.type

    if case_type == CASE_TYPE_PERSON:
        return case_id
    elif case_type == CASE_TYPE_EPISODE:
        return get_person_case_from_episode(domain, case.case_id).case_id
    elif case_type == CASE_TYPE_ADHERENCE:
        episode_case = get_episode_case_from_adherence(domain, case.case_id)
        return get_person_case_from_episode(domain, episode_case.case_id).case_id
    elif case_type == CASE_TYPE_TEST:
        occurrence_case = get_occurrence_case_from_test(domain, case.case_id)
        return get_person_case_from_occurrence(domain, occurrence_case.case_id).case_id
    elif case_type == CASE_TYPE_OCCURRENCE:
        return get_person_case_from_occurrence(domain, case.case_id).case_id
    elif case_type == CASE_TYPE_VOUCHER:
        return get_person_case_from_voucher(domain, case.case_id).case_id
    else:
        raise ENikshayCaseNotFound(u"Unknown case type: {}".format(case_type))


def _get_voucher_parent(domain, voucher_case_id):
    prescription = None
    test = None

    try:
        prescription = get_first_parent_of_case(domain, voucher_case_id, CASE_TYPE_PRESCRIPTION)
    except ENikshayCaseNotFound:
        pass
    try:
        test = get_first_parent_of_case(domain, voucher_case_id, CASE_TYPE_TEST)
    except ENikshayCaseNotFound:
        pass
    if not (prescription or test):
        raise ENikshayCaseNotFound(
            "Couldn't find any open parent prescription or test cases for id: {}".format(voucher_case_id)
        )
    assert not (prescription and test), "Didn't expect voucher to have prescription AND test parent"
    return test or prescription


def get_episode_case_from_voucher(domain, voucher_case_id):
    voucher_parent = _get_voucher_parent(domain, voucher_case_id)
    assert voucher_parent.type == CASE_TYPE_PRESCRIPTION
    episode = get_first_parent_of_case(domain, voucher_parent.case_id, CASE_TYPE_EPISODE)
    return episode


def get_person_case_from_voucher(domain, voucher_case_id):
    # Case structure could be one of these two things:
    #   person <- occurrence <- episode <- prescription <- voucher
    #   person <- occurrence <- test <- voucher
    voucher_parent = _get_voucher_parent(domain, voucher_case_id)
    if voucher_parent.type == CASE_TYPE_PRESCRIPTION:
        episode = get_first_parent_of_case(domain, voucher_parent.case_id, CASE_TYPE_EPISODE)
        return get_person_case_from_episode(domain, episode.case_id)
    else:
        assert voucher_parent.type == CASE_TYPE_TEST
        occurrence = get_occurrence_case_from_test(domain, voucher_parent.case_id)
        return get_person_case_from_occurrence(domain, occurrence.case_id)


def get_prescription_vouchers_from_episode(domain, episode_case_id):
    case_accessor = CaseAccessors(domain)
    prescription_cases = [
        case for case in case_accessor.get_reverse_indexed_cases([episode_case_id])
        if case.type == CASE_TYPE_PRESCRIPTION
    ]
    return [
        c for c in case_accessor.get_reverse_indexed_cases([case.case_id for case in prescription_cases])
        if c.type == CASE_TYPE_VOUCHER
    ]


def get_fulfilled_prescription_vouchers_from_episode(domain, episode_case_id):
    return [
        voucher for voucher in get_prescription_vouchers_from_episode(domain, episode_case_id)
        if (voucher.get_case_property("voucher_type") == CASE_TYPE_PRESCRIPTION
            and voucher.get_case_property("state") == "fulfilled")
    ]


def get_prescription_from_voucher(domain, voucher_id):
    return get_parent_of_case(domain, voucher_id, CASE_TYPE_PRESCRIPTION)
