from corehq.apps.locations.tasks import deactivate_users_at_location
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from custom.icds.location_reassignment.const import HOUSEHOLD_CASE_TYPE
from custom.icds.location_reassignment.models import Transition


def deprecate_locations(domain, old_locations, new_locations, operation):
    """
    add metadata on locations
    on old locations, add
    1. DEPRECATED_TO: [list] would be a single location except in case of a split
    2. DEPRECATION_OPERATION: this location was deprecated by a merge/split/extract/move operation
    3. DEPRECATED_AT: [dict] new location id mapped to the timestamp of deprecation performed
    for new locations location
    1. DEPRECATES: [list] append this location id on it. This would be more than one location in case of merge
    :param domain: domain name
    :param old_locations: the locations to deprecate
    :param new_locations: the location that deprecates these location
    :param operation: the operation being performed, split/merge/move/extract
    :return: errors in case of failure
    """
    transition = Transition(domain, operation, old_locations, new_locations)
    if transition.valid():
        transition.perform()
        for old_location in old_locations:
            deactivate_users_at_location(old_location.location_id)
    return transition.errors


def get_household_case_ids(domain, location_id):
    return CaseAccessorSQL.get_case_ids_in_domain_by_owners(
        domain, [location_id], case_type=HOUSEHOLD_CASE_TYPE)


def get_household_and_child_case_ids_by_owner(domain, household_case_id, owner_id, case_types=None):
    case_ids = {household_case_id}
    child_cases = get_household_child_cases_by_owner(domain, household_case_id, owner_id, case_types)
    child_case_ids = [case.case_id for case in child_cases]
    case_ids.update(child_case_ids)
    return case_ids


def get_household_child_cases_by_owner(domain, household_case_id, owner_id, case_types):
    def get_child_cases(ids):
        return [case for case in
                CaseAccessorSQL.get_reverse_indexed_cases(domain, ids)
                if case.owner_id == owner_id]

    cases = []
    parent_case_ids = [household_case_id]
    while parent_case_ids:
        child_cases = get_child_cases(parent_case_ids)
        if child_cases:
            parent_case_ids = [case.case_id for case in child_cases]
            if case_types:
                cases.extend([case for case in child_cases if case.type in case_types])
            else:
                cases.extend(child_cases)
        else:
            parent_case_ids = None
    return cases
