import pytz
from collections import namedtuple, defaultdict
from django.utils.dateparse import parse_datetime
from dateutil.parser import parse

from corehq.apps.locations.models import SQLLocation
from corehq.util.decorators import hqnottest
from casexml.apps.case.const import ARCHIVED_CASE_OWNER_ID
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.exceptions import (
    ENikshayCaseNotFound,
    ENikshayCaseTypeNotFound,
    NikshayCodeNotFound,
    NikshayLocationNotFound,
    ENikshayException,
    EnikshayBadAppState,
)
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


def get_all_occurrence_cases_from_person(domain, person_case_id):
    case_accessor = CaseAccessors(domain)
    all_cases = case_accessor.get_reverse_indexed_cases([person_case_id])
    occurrence_cases = [case for case in all_cases
                        if case.type == CASE_TYPE_OCCURRENCE]
    open_occurrence_cases = [case for case in occurrence_cases if not case.closed]
    if len(open_occurrence_cases) > 1:
        raise EnikshayBadAppState("Multiple open occurrences found for person case : %s " % person_case_id)
    return occurrence_cases


def get_open_occurrence_case_from_person(domain, person_case_id):
    """
    Gets the first open 'occurrence' case for the person

    Assumes the following case structure:
    Person <--ext-- Occurrence

    """
    occurrence_cases = get_all_occurrence_cases_from_person(domain, person_case_id)
    open_occurrence_cases = [case for case in occurrence_cases if not case.closed]
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

    return get_open_active_dstb_episode_case_from_occurrence(test_case.domain, occurrence_case_id)


def get_all_episode_cases_from_person(domain, person_case_id):
    case_accessor = CaseAccessors(domain)
    episode_cases = []
    occurrence_cases = get_all_occurrence_cases_from_person(domain, person_case_id)
    for occurrence_case in occurrence_cases:
        all_cases = case_accessor.get_reverse_indexed_cases([occurrence_case.get_id])
        episode_cases += [case for case in all_cases
                          if case.type == CASE_TYPE_EPISODE and
                          case.dynamic_case_properties().get('episode_type') == "confirmed_tb"]
    return episode_cases


def get_open_active_dstb_episode_case_from_occurrence(domain, occurrence_case_id):
    """
    In eNikshay public sector app
    Gets the first open DSTB 'episode' case for the occurrence

    Assumes the following case structure:
    Occurrence <--ext-- Episode

    """
    case_accessor = CaseAccessors(domain)
    episode_cases = case_accessor.get_reverse_indexed_cases([occurrence_case_id])
    open_active_episode_cases = [case for case in episode_cases
                                 if not case.closed and
                                 case.type == CASE_TYPE_EPISODE and
                                 case.get_case_property('episode_type') == "confirmed_tb" and
                                 case.get_case_property('is_active') == 'true'
                                 ]
    if len(open_active_episode_cases) > 1:
        raise EnikshayBadAppState("Multiple open active episode cases found for occurrence : %s" % occurrence_case_id)

    if open_active_episode_cases:
        return open_active_episode_cases[0]
    else:
        raise ENikshayCaseNotFound(
            "Occurrence with id: {} exists but has no open episode cases".format(occurrence_case_id)
        )


def get_open_drtb_hiv_case_from_occurrence(domain, occurrence_case_id):
    """
    - Get the occurrence case from the episode case
    - Get an open secondary_owner case (extension of occurrence) where secondary_owner_type = drtb-hiv"
    """
    case_accessor = CaseAccessors(domain)
    open_drtb_hivsecondary_owner_case = [
        case for case in case_accessor.get_reverse_indexed_cases([occurrence_case_id])
        if not case.closed and
        case.type == CASE_TYPE_SECONDARY_OWNER and
        case.get_case_property('secondary_owner_type') == 'drtb-hiv'
    ]
    if open_drtb_hivsecondary_owner_case:
        return open_drtb_hivsecondary_owner_case[0]
    else:
        raise ENikshayCaseNotFound(
            "Occurrence with id: {} exists but has no open drtb-hiv secondary owner case".format(
                occurrence_case_id)
        )


def get_open_episode_case_from_person(domain, person_case_id):
    """
    Gets the first open 'episode' case for the person

    Assumes the following case structure:
    Person <--ext-- Occurrence <--ext-- Episode

    """
    return get_open_active_dstb_episode_case_from_occurrence(
        domain, get_open_occurrence_case_from_person(domain, person_case_id).case_id
    )


def get_referral_cases_from_person(domain, person_case_id, closed_cases=False):
    case_accessor = CaseAccessors(domain)
    reverse_indexed_cases = case_accessor.get_reverse_indexed_cases([person_case_id])
    referral_cases = [case for case in reverse_indexed_cases
                      if case.closed == closed_cases and case.type == CASE_TYPE_REFERRAL]
    occurrence_cases = [case.case_id for case in reverse_indexed_cases
                        if case.type == CASE_TYPE_OCCURRENCE]
    reversed_indexed_occurrence = case_accessor.get_reverse_indexed_cases(occurrence_cases)
    referral_cases.extend(
        case for case in reversed_indexed_occurrence
        if case.closed == closed_cases and case.type == CASE_TYPE_REFERRAL
    )
    return referral_cases


def get_open_referral_case_from_person(domain, person_case_id):
    open_referral_cases = get_referral_cases_from_person(domain, person_case_id)
    if not open_referral_cases:
        return None
    if len(open_referral_cases) == 1:
        return open_referral_cases[0]
    else:
        raise ENikshayException(
            "Expected none or one open referral case for person with id: {}".format(person_case_id)
        )


def get_latest_closed_referral_case_from_person(domain, person_case_id, with_status=None):
    closed_referral_cases = get_referral_cases_from_person(domain, person_case_id, closed_cases=True)
    if with_status:
        closed_referral_cases = [
            referral_case for referral_case in closed_referral_cases
            if referral_case.get_case_property('referral_status') == with_status
        ]
    return sorted(closed_referral_cases, key=lambda x: x.closed_on)[0]


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
    return get_first_parent_of_case(domain, test_case_id, CASE_TYPE_OCCURRENCE)


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
    picks episode case's diagnosing_facility_id if passed else falls back to person's owner id for
    fetching the base location to get the hierarchy
    public locations hierarchy
    sto -> cto -> dto -> tu -> phi

    private locations hierarchy
    sto-> cto -> dto -> pcp
    """
    if person_case.dynamic_case_properties().get(ENROLLED_IN_PRIVATE) == 'true':
        return _get_private_locations(person_case)
    else:
        return _get_public_locations(person_case, episode_case)


def _get_public_locations(person_case, episode_case):
    PublicPersonLocationHierarchy = namedtuple('PersonLocationHierarchy', 'sto dto tu phi')
    try:
        phi_location_id = None
        if episode_case:
            phi_location_id = episode_case.dynamic_case_properties().get('diagnosing_facility_id')
        # fallback to person_case.owner_id in case diagnosing_facility_id not set on episode
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
    else:
        raise ENikshayCaseTypeNotFound(u"Unknown case type: {}".format(case_type))


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


def get_all_episode_ids(domain):
    case_accessor = CaseAccessors(domain)
    case_ids = case_accessor.get_open_case_ids_in_domain_by_type(CASE_TYPE_EPISODE)
    return case_ids


def iter_all_active_public_sector_person_from_episode_cases(domain, case_ids):
    """From a list of case_ids, return all the active episodes and associate person case
    """
    case_accessor = CaseAccessors(domain)
    episode_cases = case_accessor.iter_cases(case_ids)
    for episode_case in episode_cases:
        if episode_case.type != CASE_TYPE_EPISODE:
            continue

        if episode_case.closed:
            continue

        if episode_case.get_case_property('is_active') != 'true':
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


def get_person_case_from_test(domain, test_case_id):
    return (
        get_person_case_from_occurrence(
            domain,
            get_occurrence_case_from_test(domain, test_case_id)
        )
    )
