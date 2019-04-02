from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple
from datetime import datetime
from couchdbkit import ResourceNotFound
from casexml.apps.case.const import UNOWNED_EXTENSION_OWNER_ID
from casexml.apps.case.exceptions import IllegalCaseId
from casexml.apps.phone.exceptions import InvalidDomainError, InvalidOwnerIdError
from casexml.apps.phone.models import OwnershipCleanlinessFlag
from corehq.apps.domain.models import Domain
from corehq.apps.hqcase.dbaccessors import get_all_case_owner_ids
from corehq.apps.users.util import WEIRD_USER_IDS
from django.conf import settings
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.soft_assert import soft_assert
from dimagi.utils.logging import notify_exception
import six


FootprintInfo = namedtuple('FootprintInfo', ['base_ids', 'all_ids', 'extension_ids'])
DependentCaseInfo = namedtuple("DependentCaseInfo", ["all_ids", "extension_ids"])
DirectDependencies = namedtuple("DirectDependencies", ['all', 'indexed_cases', 'extension_cases'])
CleanlinessFlag = namedtuple('CleanlinessFlag', ['is_clean', 'hint'])


def should_track_cleanliness(domain):
    """
    Whether a domain should track cleanliness on submission.
    """
    return True


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


def set_cleanliness_flags_for_all_domains(force_full=False):
    """
    Updates cleanliness for all domains
    """
    for domain in Domain.get_all_names():
        try:
            set_cleanliness_flags_for_domain(domain, force_full=force_full)
        except InvalidDomainError as e:
            notify_exception(None, six.text_type(e))


def set_cleanliness_flags_for_domain(domain, force_full=False, raise_soft_assertions=True):
    """
    Sets all cleanliness flags for an entire domain.
    """
    for owner_id in CaseAccessors(domain).get_case_owner_ids():
        if owner_id and owner_id not in WEIRD_USER_IDS:
            try:
                set_cleanliness_flags(domain, owner_id, force_full=force_full,
                                      raise_soft_assertions=raise_soft_assertions)
            except InvalidOwnerIdError as e:
                notify_exception(None, six.text_type(e))


def _is_web_user(owner_id):
    from corehq.apps.users.models import WebUser
    try:
        document = WebUser.get_db().get(owner_id)
    except ResourceNotFound:
        document = {'doc_type': 'unknown'}
    return document.get('doc_type', None) == 'WebUser'


def set_cleanliness_flags(domain, owner_id, force_full=False, raise_soft_assertions=True):
    """
    For a given owner ID, manually sets the cleanliness flag on that ID.
    """
    if not domain or len(domain) > 100:
        raise InvalidDomainError('Domain {} must be a non-empty string less than 100 characters'.format(domain))
    if not owner_id or len(owner_id) > 100:
        raise InvalidOwnerIdError(
            'Owner ID {} must be a non-empty string less than 100 characters'.format(owner_id)
        )
    cleanliness_object = OwnershipCleanlinessFlag.objects.get_or_create(
        owner_id=owner_id,
        domain=domain,
        defaults={'is_clean': False}
    )[0]

    def needs_full_check(domain, cleanliness_obj):
        # if it already is clean we don't need to do anything since that gets invalidated on submission
        # if dirty, first check the hint and only do a full check if it's not valid
        return not cleanliness_obj.is_clean and (
            not cleanliness_obj.hint or not hint_still_valid(domain, cleanliness_obj.hint)
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

        # filter out docs where we expect this to be broken (currently just web users)
        if not _is_web_user(owner_id) and raise_soft_assertions:
            _assert = soft_assert(notify_admins=True, exponential_backoff=False, fail_if_debug=False)
            _assert(False, 'Cleanliness flags out of sync for user {} in domain {}!'.format(
                owner_id, domain
            ))

    cleanliness_object.last_checked = datetime.utcnow()
    cleanliness_object.save()


def hint_still_valid(domain, hint):
    """
    For a given domain/owner/cleanliness hint check if it's still valid
    """
    casedb = CaseAccessors(domain)
    try:
        hint_case = casedb.get_case(hint)
        hint_owner = hint_case.owner_id
    except CaseNotFound:
        # hint was deleted
        return False
    dependent_case_ids = set(get_dependent_case_info(domain, [hint]).all_ids)
    return any([c.owner_id != hint_owner and c.owner_id != UNOWNED_EXTENSION_OWNER_ID
                for c in casedb.get_cases(list(dependent_case_ids))])


def get_cleanliness_flag_from_scratch(domain, owner_id):
    casedb = CaseAccessors(domain)
    footprint_info = get_case_footprint_info(domain, owner_id)
    owned_cases = footprint_info.base_ids
    cases_to_check = footprint_info.all_ids - owned_cases
    if cases_to_check:
        closed_owned_case_ids = set(casedb.get_closed_case_ids_for_owner(owner_id))
        cases_to_check = cases_to_check - closed_owned_case_ids - footprint_info.extension_ids
        # check extension cases that are unowned or owned by others
        extension_cases_to_check = footprint_info.extension_ids - closed_owned_case_ids - owned_cases
        while extension_cases_to_check:
            extension_case = extension_cases_to_check.pop()
            dependent_cases = set(get_dependent_case_info(domain, [extension_case]).all_ids)
            unowned_dependent_cases = dependent_cases - owned_cases
            extension_cases_to_check = extension_cases_to_check - dependent_cases
            dependent_cases_owned_by_other_owners = {
                dependent_case.case_id
                for dependent_case in casedb.get_cases(list(unowned_dependent_cases))
                if dependent_case.owner_id != UNOWNED_EXTENSION_OWNER_ID
            }
            if dependent_cases_owned_by_other_owners:
                hint_id = dependent_cases & owned_cases
                # can't get back from extension case to owned case e.g. host is a child of owned case
                if hint_id:
                    return CleanlinessFlag(False, hint_id.pop())

        if cases_to_check:
            # it wasn't in any of the open or closed IDs - it must be dirty
            reverse_index_infos = casedb.get_all_reverse_indices_info(list(cases_to_check))
            reverse_index_ids = set([r.case_id for r in reverse_index_infos])
            indexed_with_right_owner = (reverse_index_ids & (owned_cases | closed_owned_case_ids))
            found_deleted_cases = False
            while indexed_with_right_owner:
                hint_id = indexed_with_right_owner.pop()
                infos_for_this_owner = _get_info_by_case_id(reverse_index_infos, hint_id)
                for info in infos_for_this_owner:
                    try:
                        case = CaseAccessors(domain).get_case(info.referenced_id)
                        if not case.is_deleted:
                            return CleanlinessFlag(False, hint_id)
                        else:
                            found_deleted_cases = True
                    except ResourceNotFound:
                        # the case doesn't exist - don't use it as a dirty flag
                        found_deleted_cases = True

            if found_deleted_cases:
                # if we made it all the way to the end of the loop without returning anything
                # then the owner was only flagged as dirty due to missing cases,
                # This implies the owner is still clean.
                return CleanlinessFlag(True, None)
            else:
                # I don't believe code can ever be hit, but if it is we should fail hard
                # until we can better understand it.
                raise IllegalCaseId('Owner {} in domain {} has an invalid index reference chain!!'.format(
                    owner_id, domain
                ))

    return CleanlinessFlag(True, None)


def _get_info_by_case_id(index_infos, case_id):
    return [i for i in index_infos if i.case_id == case_id]


def get_dependent_case_info(domain, case_ids):
    """
    Fetches all dependent cases of cases passed in.

    This includes:
     1. any cases that the passed in cases index (e.g. parent cases)
     2. any extensions of the passed in cases
     3. (1) and (2) above, for any dependencies that are pulled in
    """
    assert not isinstance(case_ids, (six.text_type, bytes))
    all_dependencies = set()
    direct_dependencies = _get_direct_dependencies(domain, case_ids)
    new_case_ids = direct_dependencies.all
    all_extensions = direct_dependencies.extension_cases
    while new_case_ids:
        all_dependencies = all_dependencies | new_case_ids
        direct_dependencies = _get_direct_dependencies(domain, list(new_case_ids))
        all_extensions = all_extensions | direct_dependencies.extension_cases
        new_case_ids = direct_dependencies.all - all_dependencies
    return DependentCaseInfo(all_ids=all_dependencies, extension_ids=all_extensions)


def _get_direct_dependencies(domain, case_ids):
    assert not isinstance(case_ids, (six.text_type, bytes))
    case_accessor = CaseAccessors(domain)
    extension_cases = set(case_accessor.get_extension_case_ids(case_ids))
    indexed_cases = set(case_accessor.get_indexed_case_ids(case_ids))
    return DirectDependencies(
        all=extension_cases | indexed_cases,
        indexed_cases=indexed_cases,
        extension_cases=extension_cases
    )


def get_case_footprint_info(domain, owner_id):
    """
    This function is duplicating a lot of functionality in get_footprint/get_related_cases.

    However it is unique in that it:
      1) starts from an owner_id instead of a base set of cases
      2) doesn't return full blown case objects but just IDs
      3) differentiates between the base set and the complete list
    """
    open_case_ids = set(CaseAccessors(domain).get_open_case_ids_for_owner(owner_id))
    dependent_cases = get_dependent_case_info(domain, open_case_ids)
    return FootprintInfo(base_ids=set(open_case_ids),  # open cases with this owner
                         all_ids=dependent_cases.all_ids | open_case_ids,
                         extension_ids=dependent_cases.extension_ids)
