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


class Transition(object):
    def __init__(self, operation, old_locations, new_locations):
        self.operation = {
            MERGE_OPERATION: MergeOperation,
            SPLIT_OPERATION: SplitOperation,
            EXTRACT_OPERATION: ExtractOperation,
            MOVE_OPERATION: MoveOperation
        }[operation](old_locations, new_locations)

    def valid(self):
        return self.operation.valid()

    def perform(self):
        return self.operation.perform()


class BaseOperation(metaclass=ABCMeta):
    type = None

    def __init__(self, old_locations, new_locations):
        self.old_locations = old_locations
        self.new_locations = new_locations

    def valid(self):
        """
        Invalid if
        1. there are no locations
        2. if any of the old locations have already been deprecated
        3. if any of the new locations has already been a part of a deprecation
        :return:
        """
        if not self.old_locations or not self.new_locations:
            return False
        for old_location in self.old_locations:
            if (DEPRECATED_TO in old_location.metadata
                    or DEPRECATED_AT in old_location.metadata
                    or DEPRECATED_VIA in old_location.metadata):
                return False
        for new_location in self.new_locations:
            if DEPRECATES in new_location.metadata:
                return False

    @abstractmethod
    def perform(self):
        raise NotImplementedError


class MergeOperation(BaseOperation):
    type = MERGE_OPERATION

    def valid(self):
        valid = super().valid()
        if not valid:
            return False
        return len(self.old_locations) > 1 and len(self.new_locations) == 1

    def perform(self):
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


class SplitOperation(BaseOperation):
    type = SPLIT_OPERATION

    def valid(self):
        valid = super().valid()
        if not valid:
            return False
        return len(self.old_locations) == 1 and len(self.new_locations) > 1

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

    def valid(self):
        valid = super().valid()
        if not valid:
            return False
        return len(self.old_locations) == 1 and len(self.new_locations) == 1

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

    def valid(self):
        valid = super().valid()
        if not valid:
            return False
        return len(self.old_locations) == 1 and len(self.new_locations) == 1

    def perform(self):
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
