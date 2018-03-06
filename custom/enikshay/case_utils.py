from __future__ import absolute_import
from __future__ import unicode_literals
import pytz
from collections import namedtuple, defaultdict
from django.utils.dateparse import (
    parse_datetime,
    parse_date,
)
from dateutil.parser import parse

from corehq.apps.locations.models import SQLLocation
from corehq.util.decorators import hqnottest
from casexml.apps.case.const import ARCHIVED_CASE_OWNER_ID
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.const import ENROLLED_IN_PRIVATE, SECTORS, PRIVATE_SECTOR, PUBLIC_SECTOR
from custom.enikshay.exceptions import (
    ENikshayCaseNotFound,
    ENikshayCaseTypeNotFound,
    NikshayCodeNotFound,
    NikshayLocationNotFound,
)
from corehq.form_processor.exceptions import CaseNotFound
import six

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
CASE_TYPE_PRESCRIPTION_ITEM = "prescription_item"
CASE_TYPE_VOUCHER = "voucher"
CASE_TYPE_DRUG_RESISTANCE = "drug_resistance"
CASE_TYPE_SECONDARY_OWNER = "secondary_owner"
CASE_TYPE_INVESTIGATION = "investigation"


def get_all_parents_of_case(domain, case_id):
    case_accessor = CaseAccessors(domain)
    try:
        if not isinstance(case_id, six.string_types):
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

    return [
        parent_case for parent_case in parent_cases
        if not parent_case.deleted
    ]


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


def get_all_occurrence_cases_from_person(domain, person_case_id):
    return CaseAccessors(domain).get_reverse_indexed_cases(
        [person_case_id], case_types=[CASE_TYPE_OCCURRENCE])


def get_open_occurrence_case_from_person(domain, person_case_id):
    """
    Gets the first open 'occurrence' case for the person

    Assumes the following case structure:
    Person <--ext-- Occurrence

    """
    open_occurrence_cases = CaseAccessors(domain).get_reverse_indexed_cases(
        [person_case_id], case_types=[CASE_TYPE_OCCURRENCE], is_closed=False)
    if not open_occurrence_cases:
        raise ENikshayCaseNotFound(
            "Person with id: {} exists but has no open occurrence cases".format(person_case_id)
        )
    return open_occurrence_cases[0]


def get_associated_episode_case_for_test(test_case, occurrence_case_id):
    """
    get associated episode case set on the test case for new structure
    if has a new_episode_id (for diagnostic -> confirmed_tb or dstb -> drtb episode transition)
        return that episode which should be a confirmed_tb/confirmed_drtb case
    elif has a episode_case_id (for follow up test cases)
        return the associated episode case only
        which should be a confirmed_tb/confirmed_drtb case
    else
        fallback to finding the open confirmed tb episode case
    """
    test_case_properties = test_case.dynamic_case_properties()
    test_case_episode_id = (
        test_case_properties.get('new_episode_case_id')
        or test_case_properties.get('episode_case_id')
    )
    if test_case_episode_id:
        accessor = CaseAccessors(test_case.domain)
        try:
            return accessor.get_case(test_case_episode_id)
        except CaseNotFound:
            raise ENikshayCaseNotFound("Could not find episode case %s associated with test %s" %
                                       (test_case_episode_id, test_case.get_id))

    return get_open_episode_case_from_occurrence(test_case.domain, occurrence_case_id)


def get_all_episode_cases_from_person(domain, person_case_id):
    occurrence_cases = get_all_occurrence_cases_from_person(domain, person_case_id)
    return [
        case for case in CaseAccessors(domain).get_reverse_indexed_cases(
            [c.case_id for c in occurrence_cases], case_types=[CASE_TYPE_EPISODE])
        if case.dynamic_case_properties().get('episode_type') == "confirmed_tb"
    ]


def get_open_episode_case_from_occurrence(domain, occurrence_case_id):
    """
    Gets the first open 'episode' case for the occurrence

    Assumes the following case structure:
    Occurrence <--ext-- Episode

    """
    open_episode_cases = CaseAccessors(domain).get_reverse_indexed_cases(
        [occurrence_case_id], case_types=[CASE_TYPE_EPISODE], is_closed=False)
    confirmed_episode_cases = [case for case in open_episode_cases
                               if case.dynamic_case_properties().get('episode_type') == "confirmed_tb"]
    if confirmed_episode_cases:
        return confirmed_episode_cases[0]
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
    open_drtb_cases = case_accessor.get_reverse_indexed_cases(
        [episode_case_id], case_types=[CASE_TYPE_DRTB_HIV_REFERRAL], is_closed=False)
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
    reverse_indexed_cases = case_accessor.get_reverse_indexed_cases(
        [person_case_id], case_types=[CASE_TYPE_REFERRAL, CASE_TYPE_OCCURRENCE], is_closed=False)
    open_referral_cases = [
        case for case in reverse_indexed_cases
        if case.type == CASE_TYPE_REFERRAL
    ]
    occurrence_case_ids = [
        case.case_id for case in reverse_indexed_cases
        if case.type == CASE_TYPE_OCCURRENCE
    ]
    open_referral_cases.extend(
        case_accessor.get_reverse_indexed_cases(
            occurrence_case_ids, case_types=[CASE_TYPE_REFERRAL], is_closed=False
        )
    )
    if not open_referral_cases:
        return None
    else:
        return min(open_referral_cases, key=(lambda case: case.opened_on))


def get_latest_trail_case_from_person(domain, person_case_id):
    case_accessor = CaseAccessors(domain)
    reverse_indexed_cases = case_accessor.get_reverse_indexed_cases(
        [person_case_id], case_types=[CASE_TYPE_TRAIL, CASE_TYPE_OCCURRENCE])
    trail_cases = [
        case for case in reverse_indexed_cases
        if case.type == CASE_TYPE_TRAIL
    ]

    # Also check for trails on the occurrence
    occurrence_case_ids = [
        case.case_id for case in reverse_indexed_cases
        if case.type == CASE_TYPE_OCCURRENCE and not case.closed
    ]
    trail_cases.extend(case_accessor.get_reverse_indexed_cases(
        occurrence_case_ids, case_types=[CASE_TYPE_TRAIL]))

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
    return get_first_parent_of_case(domain, adherence_case_id, CASE_TYPE_EPISODE)


@hqnottest
def get_occurrence_case_from_test(domain, test_case_id):
    """
        Gets the first open occurrence case for a test
        """
    return get_first_parent_of_case(domain, test_case_id, CASE_TYPE_OCCURRENCE)


@hqnottest
def get_private_diagnostic_test_cases_from_episode(domain, episode_case_id):
    """Returns all test cases for a particular episode
    """
    occurrence_case = get_occurrence_case_from_episode(domain, episode_case_id)
    indexed_cases = CaseAccessors(domain).get_reverse_indexed_cases(
        [occurrence_case.case_id], case_types=[CASE_TYPE_TEST], is_closed=False)
    open_test_cases = [
        case for case in indexed_cases
        if case.get_case_property('purpose_of_test') == 'diagnostic'
        and case.get_case_property('date_reported') is not None
        and case.get_case_property('date_reported') != ''
        and case.get_case_property('enrolled_in_private') == 'true'
    ]
    return sorted(open_test_cases, key=lambda c: c.get_case_property('date_reported'))


def get_adherence_cases_between_dates(domain, person_case_id, start_date, end_date):
    episode = get_open_episode_case_from_person(domain, person_case_id)
    case_accessor = CaseAccessors(domain)
    indexed_cases = case_accessor.get_reverse_indexed_cases(
        [episode.case_id], case_types=[CASE_TYPE_ADHERENCE], is_closed=False)
    open_pertinent_adherence_cases = [
        case for case in indexed_cases
        if (start_date.astimezone(pytz.UTC) <=
            parse_datetime(case.dynamic_case_properties().get('adherence_date')).astimezone(pytz.UTC) <=
            end_date.astimezone(pytz.UTC))
    ]

    return open_pertinent_adherence_cases


def update_case(domain, case_id, updated_properties, external_id=None,
                device_id=__name__ + ".update_case"):
    kwargs = {
        'case_id': case_id,
        'update': updated_properties,
    }
    if external_id is not None:
        kwargs['external_id'] = external_id

    post_case_blocks(
        [CaseBlock(**kwargs).as_xml()],
        {'domain': domain},
        device_id=device_id,
    )


def get_person_locations(person_case, episode_case=None):
    """
    picks episode case's treatment_initiating_facility_id if passed else falls back to person's owner id for
    fetching the base location to get the hierarchy
    public locations hierarchy
    sto -> cto -> dto -> tu -> phi

    private locations hierarchy
    sto-> cto -> dto -> pcp
    """
    if person_case.dynamic_case_properties().get(ENROLLED_IN_PRIVATE) == 'true':
        return _get_private_locations(person_case, episode_case)
    else:
        return _get_public_locations(person_case, episode_case)


def _get_public_locations(person_case, episode_case):
    PublicPersonLocationHierarchy = namedtuple('PersonLocationHierarchy', 'sto dto tu phi')
    try:
        phi_location_id = None
        if episode_case:
            phi_location_id = episode_case.dynamic_case_properties().get('treatment_initiating_facility_id')
        # fallback to person_case.owner_id in case treatment_initiating_facility_id not set on episode
        # or if no episode case was passed
        if not phi_location_id:
            phi_location_id = person_case.owner_id
        phi_location = SQLLocation.active_objects.get(domain=person_case.domain, location_id=phi_location_id)
    except SQLLocation.DoesNotExist:
        raise NikshayLocationNotFound(
            """Location with id {location_id} not found.
            This is the diagnosing facility id for person with id: {person_id}"""
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


def _get_private_locations(person_case, episode_case=None):
    """
    if episode case is passed
    - find the location id as episode_treating_hospital on episode
     - if this location has nikshay code
      - consider this as the pcp
     - else
      - fallback to owner id as the pcp itself
    """
    PrivatePersonLocationHierarchy = namedtuple('PersonLocationHierarchy', 'sto dto pcp tu')
    pcp_location = None
    if episode_case:
        episode_treating_hospital = episode_case.get_case_property('episode_treating_hospital')
        if episode_treating_hospital:
            pcp_location = SQLLocation.active_objects.get_or_None(
                location_id=episode_treating_hospital)
            if pcp_location:
                if not pcp_location.metadata.get('nikshay_code'):
                    pcp_location = None
    if not pcp_location:
        try:
            pcp_location = SQLLocation.active_objects.get(
                domain=person_case.domain, location_id=person_case.owner_id)
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
        dto_code = district_location.metadata['nikshay_code']
        # HACK: remove this when we have all of the "HE ids" imported from Nikshay
        pcp_code = pcp_location.metadata.get('nikshay_code') or None
        # append 0 in beginning to make the code 6-digit
        if pcp_code and len(pcp_code) == 5:
            pcp_code = '0' + pcp_code
        if not dto_code:
            dto_code = pcp_location.metadata.get('rntcp_district_code')
        return PrivatePersonLocationHierarchy(
            sto=state_location.metadata['nikshay_code'],
            dto=dto_code,
            pcp=pcp_code,
            tu=tu_location_nikshay_code
        )
    except (KeyError, AttributeError) as e:
        raise NikshayCodeNotFound("Nikshay codes not found: {}".format(e))


@hqnottest
def get_lab_referral_from_test(domain, test_case_id):
    case_accessor = CaseAccessors(domain)
    lab_referral_cases = case_accessor.get_reverse_indexed_cases(
        [test_case_id], case_types=[CASE_TYPE_LAB_REFERRAL])
    if lab_referral_cases:
        return lab_referral_cases[0]
    else:
        raise ENikshayCaseNotFound(
            "test with id: {} exists but has no lab referral cases".format(test_case_id)
        )


def get_person_case_from_lab_referral(domain, lab_referral_case_id):
    test_case = get_first_parent_of_case(domain, lab_referral_case_id, CASE_TYPE_TEST)
    occurrence_case = get_occurrence_case_from_test(domain, test_case.case_id)
    return get_person_case_from_occurrence(domain, occurrence_case.case_id)


def get_person_case_from_prescription(domain, prescription_case_id):
    episode_case = get_first_parent_of_case(domain, prescription_case_id, CASE_TYPE_EPISODE)
    return get_person_case_from_episode(domain, episode_case.case_id)


def get_person_case_from_prescription_item(domain, prescription_item_case_id):
    prescription_case = get_first_parent_of_case(domain, prescription_item_case_id, CASE_TYPE_PRESCRIPTION)
    return get_person_case_from_prescription(domain, prescription_case.case_id)


def get_person_case_from_referral(domain, referral_case_id):
    occurrence_case = get_first_parent_of_case(domain, referral_case_id, CASE_TYPE_OCCURRENCE)
    return get_person_case_from_occurrence(domain, occurrence_case.case_id)


def get_person_case_from_trail(domain, trail_case_id):
    occurrence_case = get_first_parent_of_case(domain, trail_case_id, CASE_TYPE_OCCURRENCE)
    return get_person_case_from_occurrence(domain, occurrence_case.case_id)


def get_adherence_cases_from_episode(domain, episode_case_id):
    return CaseAccessors(domain).get_reverse_indexed_cases(
        [episode_case_id], case_types=[CASE_TYPE_ADHERENCE])


def get_adherence_cases_by_day(domain, episode_case_id):
    adherence_cases = get_adherence_cases_from_episode(domain, episode_case_id)

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
        return case
    elif case_type == CASE_TYPE_EPISODE:
        return get_person_case_from_episode(domain, case.case_id)
    elif case_type == CASE_TYPE_ADHERENCE:
        episode_case = get_episode_case_from_adherence(domain, case.case_id)
        return get_person_case_from_episode(domain, episode_case.case_id)
    elif case_type == CASE_TYPE_TEST:
        occurrence_case = get_occurrence_case_from_test(domain, case.case_id)
        return get_person_case_from_occurrence(domain, occurrence_case.case_id)
    elif case_type == CASE_TYPE_OCCURRENCE:
        return get_person_case_from_occurrence(domain, case.case_id)
    elif case_type == CASE_TYPE_VOUCHER:
        return get_person_case_from_voucher(domain, case.case_id)
    elif case_type == CASE_TYPE_LAB_REFERRAL:
        return get_person_case_from_lab_referral(domain, case.case_id)
    elif case_type == CASE_TYPE_PRESCRIPTION:
        return get_person_case_from_prescription(domain, case.case_id)
    elif case_type == CASE_TYPE_PRESCRIPTION_ITEM:
        return get_person_case_from_prescription_item(domain, case.case_id)
    elif case_type == CASE_TYPE_REFERRAL:
        return get_person_case_from_referral(domain, case.case_id)
    elif case_type == CASE_TYPE_TRAIL:
        return get_person_case_from_trail(domain, case.case_id)
    else:
        raise ENikshayCaseTypeNotFound("Unknown case type: {}".format(case_type))


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
    prescription_cases = case_accessor.get_reverse_indexed_cases(
        [episode_case_id], case_types=[CASE_TYPE_PRESCRIPTION])
    return case_accessor.get_reverse_indexed_cases(
        [case.case_id for case in prescription_cases], case_types=[CASE_TYPE_VOUCHER])


def get_fulfilled_prescription_vouchers_from_episode(domain, episode_case_id):
    return [
        voucher for voucher in get_prescription_vouchers_from_episode(domain, episode_case_id)
        if (voucher.get_case_property("voucher_type") == CASE_TYPE_PRESCRIPTION
            and voucher.get_case_property("state") == "fulfilled")
    ]


def get_prescription_from_voucher(domain, voucher_id):
    return get_first_parent_of_case(domain, voucher_id, CASE_TYPE_PRESCRIPTION)


def get_all_episode_ids(domain):
    case_accessor = CaseAccessors(domain)
    case_ids = case_accessor.get_open_case_ids_in_domain_by_type(CASE_TYPE_EPISODE)
    return case_ids


def get_sector(case):
    valid_types = [CASE_TYPE_EPISODE, CASE_TYPE_PERSON]
    if case.type not in valid_types:
        raise ValueError('Must pass in an {} case'.format(", ".join(valid_types)))
    if case.get_case_property(ENROLLED_IN_PRIVATE) == 'true':
        return PRIVATE_SECTOR
    return PUBLIC_SECTOR


def iter_all_active_person_episode_cases(domain, case_ids, sector=None):
    """From a list of case_ids, return all the active episodes and associate person case
    """
    if sector is not None and sector not in SECTORS:
        raise ValueError('sector argument should be one of {}, or None'.format(SECTORS))

    case_accessor = CaseAccessors(domain)
    episode_cases = case_accessor.iter_cases(case_ids)
    for episode_case in episode_cases:
        if episode_case.type != CASE_TYPE_EPISODE:
            continue

        if episode_case.closed:
            continue

        if sector == PRIVATE_SECTOR and episode_case.get_case_property(ENROLLED_IN_PRIVATE) != 'true':
            continue
        elif sector == PUBLIC_SECTOR and episode_case.get_case_property(ENROLLED_IN_PRIVATE) == 'true':
            continue

        try:
            person_case = get_person_case_from_episode(domain, episode_case.case_id)
        except ENikshayCaseNotFound:
            continue

        if person_case.owner_id == ARCHIVED_CASE_OWNER_ID:
            continue

        if person_case.closed:
            continue

        yield person_case, episode_case


def person_has_any_nikshay_notifiable_episode(person_case):
    domain = person_case.domain
    from custom.enikshay.integrations.utils import is_valid_person_submission
    from custom.enikshay.integrations.nikshay.repeaters import valid_nikshay_patient_registration

    if not is_valid_person_submission(person_case):
        return False

    episode_cases = get_all_episode_cases_from_person(domain, person_case.case_id)
    return any(valid_nikshay_patient_registration(episode_case.dynamic_case_properties())
               for episode_case in episode_cases)


def get_most_recent_referral_case_from_person(domain, person_case_id):
    case_accessor = CaseAccessors(domain)
    reverse_indexed_cases = case_accessor.get_reverse_indexed_cases(
        [person_case_id], case_types=[CASE_TYPE_REFERRAL, CASE_TYPE_OCCURRENCE])
    open_referral_cases = [
        case for case in reverse_indexed_cases
        if case.type == CASE_TYPE_REFERRAL
    ]
    occurrence_case_ids = [
        case.case_id for case in reverse_indexed_cases
        if not case.closed and case.type == CASE_TYPE_OCCURRENCE
    ]
    open_referral_cases.extend(
        case_accessor.get_reverse_indexed_cases(
            occurrence_case_ids, case_types=[CASE_TYPE_REFERRAL]))
    valid_referral_cases = [
        case for case in open_referral_cases if (
            case.dynamic_case_properties().get('referral_closed_reason') != 'duplicate_referral_reconciliation'
        )
    ]
    if not valid_referral_cases:
        return None
    else:
        return max(valid_referral_cases, key=(lambda case: case.opened_on))


def get_most_recent_episode_case_from_person(domain, person_case_id):
    occurrence_cases = get_all_occurrence_cases_from_person(domain, person_case_id)
    episode_cases = [
        case for case in CaseAccessors(domain).get_reverse_indexed_cases(
            [c.case_id for c in occurrence_cases], case_types=[CASE_TYPE_EPISODE])
        if case.dynamic_case_properties().get('close_reason') not in [
            'invalid_episode', 'duplicate', 'invalid_registration'
        ]
    ]
    if not episode_cases:
        return None
    else:
        return max(episode_cases, key=(lambda case: case.opened_on))


def get_all_vouchers_from_person(domain, person_case):
    """Returns all voucher cases under tests or prescriptions"""
    accessor = CaseAccessors(domain)
    potential_voucher_parents = []
    episode_ids = []
    occurrence_case_ids = [
        occurrence_case.case_id
        for occurrence_case in accessor.get_reverse_indexed_cases(
            [person_case.case_id], case_types=[CASE_TYPE_OCCURRENCE])
    ]
    for case in accessor.get_reverse_indexed_cases(
            occurrence_case_ids, case_types=[CASE_TYPE_TEST, CASE_TYPE_EPISODE]):
        if case.type == CASE_TYPE_TEST:
            potential_voucher_parents.append(case.case_id)
        if case.type == CASE_TYPE_EPISODE:
            episode_ids.append(case.case_id)

    potential_voucher_parents.extend(
        prescription_case.case_id
        for prescription_case in accessor.get_reverse_indexed_cases(
            episode_ids, case_types=[CASE_TYPE_PRESCRIPTION])
    )
    return accessor.get_reverse_indexed_cases(
        potential_voucher_parents, case_types=[CASE_TYPE_VOUCHER])


def get_adherence_cases_by_date(adherence_cases):
    adherence_cases_by_date = defaultdict(list)
    for case in adherence_cases:
        adherence_date = case.get('adherence_date')
        if adherence_date:
            adherence_date = parse_date(case['adherence_date']) or parse_datetime(case['adherence_date']).date()
            adherence_cases_by_date[adherence_date].append(case)
    return adherence_cases_by_date
