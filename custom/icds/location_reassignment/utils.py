from corehq.apps.locations.tasks import deactivate_users_at_location
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
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


def get_household_and_child_case_ids_by_owner(domain, household_case_id, owner_id):
    def get_child_case_ids(ids):
        return [case.case_id for case in CaseAccessorSQL.get_reverse_indexed_cases(domain, ids)
                if case.owner_id == owner_id]

    all_child_case_ids = {household_case_id}
    case_ids = [household_case_id]

    while case_ids:
        child_case_ids = get_child_case_ids(case_ids)
        if child_case_ids:
            all_child_case_ids.update(child_case_ids)
            case_ids = child_case_ids
        else:
            case_ids = None
    return all_child_case_ids
