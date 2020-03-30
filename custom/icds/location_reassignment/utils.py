from corehq.apps.locations.tasks import deactivate_users_at_location
from custom.icds.location_reassignment.models import Transition


def deprecate_locations(old_locations, new_locations, operation):
    """
    add metadata on locations
    on old locations, add
    1. DEPRECATED_TO: [list] would be a single location except in case of a split
    2. DEPRECATION_OPERATION: this location was deprecated by a merge/split/extract/move operation
    3. DEPRECATED_AT: [dict] new location id mapped to the timestamp of deprecation performed
    for new locations location
    1. DEPRECATES: [list] append this location id on it. This would be more than one location in case of merge
    :param old_locations: the locations to deprecate
    :param new_locations: the location that deprecates these location
    :param operation: the operation being performed, split/merge/move/extract
    :return: True for success, False in case of failure
    """
    transition = Transition(operation, old_locations, new_locations)
    if transition.valid():
        transition.perform()
        for old_location in old_locations:
            deactivate_users_at_location(old_location.location_id)
        return True
    return False
