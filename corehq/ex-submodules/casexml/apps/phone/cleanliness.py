from collections import namedtuple
from datetime import datetime
from couchdbkit import ResourceNotFound
from casexml.apps.case.dbaccessors import get_reverse_indexed_case_ids, get_indexed_case_ids
from casexml.apps.case.exceptions import IllegalCaseId
from casexml.apps.case.util import get_indexed_cases
from casexml.apps.phone.models import OwnershipCleanlinessFlag
from corehq.apps.domain.models import Domain
from corehq.apps.hqcase.dbaccessors import get_open_case_ids, \
    get_closed_case_ids, get_all_case_owner_ids
from corehq.apps.users.util import WEIRD_USER_IDS
from corehq.toggles import OWNERSHIP_CLEANLINESS
from django.conf import settings
from corehq.util.soft_assert import soft_assert
from dimagi.utils.couch.database import get_db


FootprintInfo = namedtuple('FootprintInfo', ['base_ids', 'all_ids'])
CleanlinessFlag = namedtuple('CleanlinessFlag', ['is_clean', 'hint'])


def should_track_cleanliness(domain):
    """
    Whether a domain should track cleanliness on submission.
    """
    if settings.UNIT_TESTING:
        override = getattr(
            settings, 'TESTS_SHOULD_TRACK_CLEANLINESS', None)
        if override is not None:
            return override

    return domain and OWNERSHIP_CLEANLINESS.enabled(domain)


def should_create_flags_on_submission(domain):
    """
    Whether a domain should create default cleanliness flags on submission.

    Right now this is only ever true for tests, though that might change once we more fully
    switch over to this restore model (requires having a complete set of existing cleanliness
    flags already in the database).
    """
    if settings.UNIT_TESTING:
        override = getattr(
            settings, 'TESTS_SHOULD_TRACK_CLEANLINESS', None)
        if override is not None:
            return override
    return False


def set_cleanliness_flags_for_enabled_domains(force_full=False):
    """
    Updates cleanliness for all domains that have the toggle enabled
    """
    for domain in Domain.get_all_names():
        if OWNERSHIP_CLEANLINESS.enabled(domain):
            set_cleanliness_flags_for_domain(domain, force_full=force_full)


def set_cleanliness_flags_for_domain(domain, force_full=False):
    """
    Sets all cleanliness flags for an entire domain.
    """
    for owner_id in get_all_case_owner_ids(domain):
        if owner_id and owner_id not in WEIRD_USER_IDS:
            set_cleanliness_flags(domain, owner_id, force_full=force_full)


def set_cleanliness_flags(domain, owner_id, force_full=False):
    """
    For a given owner ID, manually sets the cleanliness flag on that ID.
    """
    assert owner_id, "Can't set cleanliness flags for null or blank owner ids"
    cleanliness_object = OwnershipCleanlinessFlag.objects.get_or_create(
        owner_id=owner_id,
        domain=domain,
        defaults={'is_clean': False}
    )[0]

    def needs_full_check(domain, cleanliness_obj):
        # if it already is clean we don't need to do anything since that gets invalidated on submission
        return (
            # if clean, only check if the toggle is not enabled since then it won't be properly invalidated
            # on submission
            cleanliness_obj.is_clean and not OWNERSHIP_CLEANLINESS.enabled(domain)
        ) or (
            # if dirty, first check the hint and only do a full check if it's not valid
            not cleanliness_object.is_clean and (
                not cleanliness_object.hint or not hint_still_valid(domain, owner_id, cleanliness_object.hint)
            )
        )

    needs_check = needs_full_check(domain, cleanliness_object)
    previous_clean_flag = cleanliness_object.is_clean
    if force_full or needs_check:
        # either the hint wasn't set, wasn't valid or we're forcing a rebuild - rebuild from scratch
        cleanliness_flag = get_cleanliness_flag_from_scratch(domain, owner_id)
        cleanliness_object.is_clean = cleanliness_flag.is_clean
        cleanliness_object.hint = cleanliness_flag.hint

    if force_full and not needs_check and previous_clean_flag and not cleanliness_object.is_clean:
        # we went from clean to dirty and would not have checked except that we forced it
        # this seems to indicate a problem in the logic that invalidates the flag, unless the feature
        # flag was turned off for the domain. either way cory probably wants to know.
        try:
            document = get_db().get(owner_id)
        except ResourceNotFound:
            document = {'doc_type': 'unknown'}

        owner_doc_type = document.get('doc_type', None)
        # filter out docs where we expect this to be broken (currently just web users)
        if owner_doc_type != 'WebUser':
            _assert = soft_assert(to=['czue' + '@' + 'dimagi.com'], exponential_backoff=False, fail_if_debug=False)
            _assert(False, 'Cleanliness flags out of sync for a {} with id {} in domain {}!'.format(
                owner_doc_type, owner_id, domain
            ))

    else:
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
        closed_owned_case_ids = set(get_closed_case_ids(domain, owner_id))
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
    open_case_ids = get_open_case_ids(domain, owner_id)
    new_case_ids = set(open_case_ids)
    while new_case_ids:
        all_case_ids = all_case_ids | new_case_ids
        referenced_case_ids = get_indexed_case_ids(domain, list(new_case_ids))
        new_case_ids = set(referenced_case_ids) - all_case_ids

    return FootprintInfo(base_ids=set(open_case_ids), all_ids=all_case_ids)
