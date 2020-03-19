from django.db import transaction

from corehq.apps.locations.tasks import deactivate_users_at_location
from custom.icds.location_rationalization.const import (
    DEPRECATED_AT,
    DEPRECATED_TO,
    DEPRECATES,
    DEPRECATION_OPERATION,
)


def deprecate_location(location, other_location, operation, archive=True):
    """
    add metadata on locations
    on location, add
    1. DEPRECATED_TO: this can be a single location or a list like in case of a split
    2. DEPRECATION_OPERATION: this location was deprecated by a merge/split/extract/move operation
    3.DEPRECATED_AT: In case of split, since multiple locations will deprecate it, this would be a dict
    with new location id mapped to the timestamp of deprecation performed
    for other location
    1. deprecates: note this location id on it. This can hold multiple values like in case of a merge a new
    location would come from multiple locations
    :param location: the location to deprecate
    :param other_location: the location that deprecates this location
    :param operation: the operation being performed, split/merge/move/extract
    :param archive: to archive this location or not
    :return: True for success, False in case of failure
    """
    other_location_id = other_location.location_id
    if DEPRECATED_TO in location.metadata:
        location.metadata[DEPRECATED_TO].append(other_location_id)
    else:
        location.metadata[DEPRECATED_TO] = [other_location_id]
    if DEPRECATION_OPERATION in location.metadata and location.metadata[DEPRECATION_OPERATION] != operation:
        # ToDo: raise an error
        return False
    location.metadata[DEPRECATION_OPERATION] = operation
    location.metadata[DEPRECATED_AT] = {other_location_id: datetime.utcnow()}
    if archive:
        location.is_archived = True
    if DEPRECATES in other_location.metadata:
        other_location.metadata[DEPRECATES].append(location.location_id)
    else:
        other_location.metadata[DEPRECATES] = location.location_id
    with transaction.atomic():
        location.save()
        other_location.save()
    deactivate_users_at_location(location.location_id)
