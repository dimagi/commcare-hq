from collections import namedtuple
from datetime import datetime
from casexml.apps.case.dbaccessors import get_all_case_owner_ids, get_open_case_ids, get_closed_case_ids, \
    get_reverse_indexed_case_ids, get_indexed_case_ids
from casexml.apps.case.exceptions import IllegalCaseId
from casexml.apps.case.util import get_indexed_cases
from casexml.apps.phone.models import OwnershipCleanlinessFlag
from corehq.apps.users.util import WEIRD_USER_IDS


FootprintInfo = namedtuple('FootprintInfo', ['base_ids', 'all_ids'])
CleanlinessFlag = namedtuple('CleanlinessFlag', ['is_clean', 'hint'])


def set_cleanliness_flags_for_domain(domain):
    """
    Sets all cleanliness flags for an entire domain.
    """
    for owner_id in get_all_case_owner_ids(domain):
        if owner_id not in WEIRD_USER_IDS:
            set_cleanliness_flags(domain, owner_id)


def set_cleanliness_flags(domain, owner_id):
    """
    For a given owner ID, manually sets the cleanliness flag on that ID.
    """
    cleanliness_object = OwnershipCleanlinessFlag.objects.get_or_create(
        owner_id=owner_id,
        domain=domain,
        defaults={'is_clean': False}
    )[0]
    # if it already is clean we don't need to do anything since that gets invalidated on submission
    if not cleanliness_object.is_clean:
        if not cleanliness_object.hint or not hint_still_valid(domain, owner_id, cleanliness_object.hint):
            # either the hint wasn't set or wasn't valid - rebuild from scratch
            cleanliness_flag = get_cleanliness_flag_from_scratch(domain, owner_id)
            cleanliness_object.is_clean = cleanliness_flag.is_clean
            cleanliness_object.hint = cleanliness_flag.hint

    cleanliness_object.last_checked = datetime.utcnow()
    cleanliness_object.save()


def hint_still_valid(domain, owner_id, hint):
    """
    For a given domain/owner/cleanliness hint check if it's still valid
    """
    related_cases = get_indexed_cases(domain, [hint])
    return any([c.owner_id != owner_id for c in related_cases])


def get_cleanliness_flag_from_scratch(domain, owner_id):
    footprint_info = get_case_footprint_info(domain, owner_id)
    cases_to_check = footprint_info.all_ids - footprint_info.base_ids
    if cases_to_check:
        closed_owned_case_ids = set(get_closed_case_ids(owner_id))
        cases_to_check = cases_to_check - closed_owned_case_ids
        if cases_to_check:
            # it wasn't in any of the open or closed IDs - it must be dirty
            reverse_index_ids = set(get_reverse_indexed_case_ids(domain, list(cases_to_check)))
            indexed_with_right_owner = (reverse_index_ids & (footprint_info.base_ids | closed_owned_case_ids))
            if indexed_with_right_owner:
                return CleanlinessFlag(False, indexed_with_right_owner.pop())

            # I'm not sure if this code can ever be hit, but if it is we should fail hard
            # until we can better understand it.
            raise IllegalCaseId('Owner {} in domain {} has an invalid index reference chain!!'.format(
                owner_id, domain
            ))

    return CleanlinessFlag(True, None)


def get_case_footprint_info(domain, owner_id):
    """
    This function is duplicating a lot of functionality in get_footprint/get_related_cases.

    However it is unique in that it:
      1) starts from an owner_id instead of a base set of cases
      2) doesn't return full blown case objects but just IDs
      3) differentiates between the base set and the complete list
    """
    all_case_ids = set()
    # get base set of cases (anything open with this owner id)
    open_case_ids = get_open_case_ids(owner_id)
    new_case_ids = set(open_case_ids)
    while new_case_ids:
        all_case_ids = all_case_ids | new_case_ids
        referenced_case_ids = get_indexed_case_ids(domain, list(new_case_ids))
        new_case_ids = set(referenced_case_ids) - all_case_ids

    return FootprintInfo(base_ids=set(open_case_ids), all_ids=all_case_ids)
