from abc import ABCMeta, abstractmethod
from datetime import datetime

from django.db import transaction

from custom.icds.location_reassignment.const import (
    DEPRECATED_AT,
    DEPRECATED_TO,
    DEPRECATED_VIA,
    DEPRECATES,
    DEPRECATES_AT,
    DEPRECATES_VIA,
    EXTRACT_OPERATION,
    MERGE_OPERATION,
    MOVE_OPERATION,
    SPLIT_OPERATION,
)

ONE = "one"
MANY = "many"


class Transition(object):
    # Fails if operation fails
    def __init__(self, domain, operation, old_locations, new_locations):
        self.operation = {
            MERGE_OPERATION: MergeOperation,
            SPLIT_OPERATION: SplitOperation,
            EXTRACT_OPERATION: ExtractOperation,
            MOVE_OPERATION: MoveOperation
        }[operation](domain, old_locations, new_locations)

    def valid(self):
        return self.operation.valid()

    def perform(self):
        return self.operation.perform()

    @property
    def errors(self):
        return self.operation.errors


class BaseOperation(metaclass=ABCMeta):
    type = None
    expected_old_locations = ONE
    expected_new_locations = ONE

    def __init__(self, domain, old_locations, new_locations):
        self.domain = domain
        self.old_locations = old_locations
        self.new_locations = new_locations
        self.errors = []

    def valid(self):
        """
        Invalid if
        1. there are no locations
        2. if any of the old locations has already been deprecated
        3. if any of the new locations has already been a part of a deprecation
        4. the count of old and new locations is not as expected for the operation
        :return:
        """
        if not self.old_locations or not self.new_locations:
            self.errors.append("Missing old or new locations.")
            return False
        valid = True
        for old_location in self.old_locations:
            if (old_location.metadata.get(DEPRECATED_TO)
                    or old_location.metadata.get(DEPRECATED_AT)
                    or old_location.metadata.get(DEPRECATED_VIA)):
                self.errors.append("%s operation: location %s with site code %s is already deprecated." % (
                    self.type, old_location.name, old_location.site_code))
                valid = False
        for new_location in self.new_locations:
            if (new_location.metadata.get(DEPRECATES)
                    or new_location.metadata.get(DEPRECATES_AT)
                    or new_location.metadata.get(DEPRECATES_VIA)):
                self.errors.append("%s operation: location %s with site code %s is already deprecated." % (
                    self.type, new_location.name, new_location.site_code))
                valid = False
        valid = valid and self._validate_location_count(self.expected_old_locations,
                                                        len(self.old_locations), "old")
        valid = valid and self._validate_location_count(self.expected_new_locations,
                                                        len(self.new_locations), "new")
        return valid

    def _validate_location_count(self, expected, count, location_type):
        valid = True
        if expected == MANY and count == 1:
            self.errors.append("%s operation: Got only one %s location." % (self.type, location_type))
            valid = False
        elif expected == ONE and count > 1:
            self.errors.append("%s operation: Got %s %s location." % (self.type, count, location_type))
            valid = False
        return valid

    @abstractmethod
    def perform(self):
        raise NotImplementedError


class MergeOperation(BaseOperation):
    type = MERGE_OPERATION
    expected_old_locations = MANY

    def perform(self):
        from custom.icds.location_reassignment.tasks import reassign_household_and_child_cases_for_owner
        with transaction.atomic():
            timestamp = datetime.utcnow()
            new_location = self.new_locations[0]
            for old_location in self.old_locations:
                old_location.metadata[DEPRECATED_TO] = [new_location.location_id]
                old_location.metadata[DEPRECATED_AT] = timestamp
                old_location.metadata[DEPRECATED_VIA] = self.type
                old_location.is_archived = True
                old_location.save()

            new_location.metadata[DEPRECATES] = [l.location_id for l in self.old_locations]
            new_location.metadata[DEPRECATES_AT] = timestamp
            new_location.metadata[DEPRECATES_VIA] = self.type
            new_location.save()
        for old_location in self.old_locations:
            reassign_household_and_child_cases_for_owner.delay(self.domain, old_location.location_id,
                                                               new_location.location_id, timestamp)


class SplitOperation(BaseOperation):
    type = SPLIT_OPERATION
    expected_new_locations = MANY

    def perform(self):
        with transaction.atomic():
            timestamp = datetime.utcnow()
            old_location = self.old_locations[0]
            old_location.metadata[DEPRECATED_TO] = [l.location_id for l in self.new_locations]
            old_location.metadata[DEPRECATED_AT] = timestamp
            old_location.metadata[DEPRECATED_VIA] = self.type
            old_location.is_archived = True
            old_location.save()

            for new_location in self.new_locations:
                new_location.metadata[DEPRECATES] = [old_location.location_id]
                new_location.metadata[DEPRECATES_AT] = timestamp
                new_location.metadata[DEPRECATES_VIA] = self.type
                new_location.save()


class ExtractOperation(BaseOperation):
    type = EXTRACT_OPERATION

    def perform(self):
        with transaction.atomic():
            timestamp = datetime.utcnow()
            old_location = self.old_locations[0]
            new_location = self.new_locations[0]
            old_location.metadata[DEPRECATED_TO] = [new_location.location_id]
            old_location.metadata[DEPRECATED_AT] = timestamp
            old_location.metadata[DEPRECATED_VIA] = self.type
            old_location.save()

            new_location.metadata[DEPRECATES] = [old_location.location_id]
            new_location.metadata[DEPRECATES_AT] = timestamp
            new_location.metadata[DEPRECATES_VIA] = self.type
            new_location.save()


class MoveOperation(BaseOperation):
    type = MOVE_OPERATION

    def perform(self):
        from custom.icds.location_reassignment.tasks import reassign_household_and_child_cases_for_owner
        with transaction.atomic():
            timestamp = datetime.utcnow()
            old_location = self.old_locations[0]
            new_location = self.new_locations[0]
            old_location.metadata[DEPRECATED_TO] = [new_location.location_id]
            old_location.metadata[DEPRECATED_AT] = timestamp
            old_location.metadata[DEPRECATED_VIA] = self.type
            old_location.is_archived = True
            old_location.save()

            new_location.metadata[DEPRECATES] = [old_location.location_id]
            new_location.metadata[DEPRECATES_AT] = timestamp
            new_location.metadata[DEPRECATES_VIA] = self.type
            new_location.save()
        reassign_household_and_child_cases_for_owner.delay(self.domain, old_location.location_id,
                                                           new_location.location_id, timestamp)
