from abc import ABCMeta, abstractmethod
from datetime import datetime

from django.db import transaction
from django.utils.functional import cached_property

import attr
from memoized import memoized

from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.locations.tasks import deactivate_users_at_location
from custom.icds.location_reassignment.const import (
    DEPRECATED_AT,
    DEPRECATED_TO,
    DEPRECATED_VIA,
    DEPRECATES,
    DEPRECATES_AT,
    DEPRECATES_VIA,
    EXTRACT_OPERATION,
    LGD_CODE,
    MAP_LOCATION_NAME,
    MERGE_OPERATION,
    MOVE_OPERATION,
    SPLIT_OPERATION,
)
from custom.icds.location_reassignment.exceptions import InvalidTransitionError

ONE = "one"
MANY = "many"


@attr.s
class Transition(object):
    # Fails if operation fails
    domain = attr.ib()
    location_type_code = attr.ib()
    operation = attr.ib()
    old_site_codes = attr.ib(factory=list)
    new_site_codes = attr.ib(factory=list)
    new_location_details = attr.ib(factory=dict)
    user_transitions = attr.ib(factory=dict)

    def add(self, old_site_code, new_site_code, new_location_details, old_username, new_username):
        """
        all operations should be only added via this method
        """
        # it would be nice to keep order so use list instead of set
        if old_site_code not in self.old_site_codes:
            self.old_site_codes.append(old_site_code)
        if new_site_code not in self.new_site_codes:
            self.new_site_codes.append(new_site_code)
        self.new_location_details[new_site_code] = new_location_details
        if old_username and new_username:
            self.user_transitions[old_username] = new_username

    @cached_property
    def operation_obj(self):
        return {
            MERGE_OPERATION: MergeOperation,
            SPLIT_OPERATION: SplitOperation,
            EXTRACT_OPERATION: ExtractOperation,
            MOVE_OPERATION: MoveOperation
        }[self.operation](self.domain, self.old_site_codes, self.new_site_codes)

    @transaction.atomic()
    def perform(self):
        if not self.valid():
            raise InvalidTransitionError(", ".join(self.errors))
        new_locations_created = self._create_missing_new_locations()
        self.operation_obj.new_locations.extend(new_locations_created)
        self.operation_obj.perform()
        if self.operation_obj.deactivates_old_users:
            for old_location in self.operation_obj.old_locations:
                deactivate_users_at_location(old_location.location_id)

    def valid(self):
        return self.operation_obj.valid()

    @property
    def errors(self):
        return self.operation_obj.errors

    def _create_missing_new_locations(self):
        site_codes_present = (
            SQLLocation.active_objects.filter(domain=self.domain, site_code__in=self.new_site_codes)
            .values_list('site_code', flat=True))
        new_locations = []
        for site_code in self.new_site_codes:
            if site_code not in site_codes_present:
                if site_code not in self.new_location_details:
                    raise InvalidTransitionError(f"Missing details for new location {site_code}")
                details = self.new_location_details[site_code]
                parent_location = None
                if details['parent_site_code']:
                    parent_location = self._get_parent_location(details['parent_site_code'])
                metadata = {}
                if details['lgd_code']:
                    metadata[LGD_CODE] = details['lgd_code']
                if details['sub_district_name']:
                    metadata[MAP_LOCATION_NAME] = details['sub_district_name']
                new_locations.append(SQLLocation.objects.create(
                    domain=self.domain, site_code=site_code, name=details['name'],
                    parent=parent_location,
                    location_type=self._location_type,
                    metadata=metadata
                ))
        return new_locations

    @memoized
    def _get_parent_location(self, site_code):
        return SQLLocation.active_objects.get(domain=self.domain, site_code=site_code)

    @cached_property
    def _location_type(self):
        return LocationType.objects.get(domain=self.domain, code=self.location_type_code)


class BaseOperation(metaclass=ABCMeta):
    type = None
    deactivates_old_users = True
    archives_old_locations = True
    expected_old_locations = ONE
    expected_new_locations = ONE

    def __init__(self, domain, old_site_codes, new_site_codes):
        self.domain = domain
        self.old_site_codes = old_site_codes
        self.new_site_codes = new_site_codes
        self.old_locations = []
        self.new_locations = []
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
        if not self.old_site_codes or not self.new_site_codes:
            self.errors.append("Missing old or new site codes.")
            return False

        valid = (
            self._validate_location_count(self.expected_old_locations, len(self.old_site_codes), "old")
            and self._validate_location_count(self.expected_new_locations, len(self.new_site_codes), "new")
        )
        if not valid:
            return False

        self.old_locations = list(SQLLocation.active_objects.filter(domain=self.domain,
                                                                    site_code__in=self.old_site_codes))
        if len(self.old_site_codes) != len(self.old_locations):
            missing_site_codes = set(self.old_site_codes) - set([l.site_code for l in self.old_locations])
            if missing_site_codes:
                raise InvalidTransitionError("Could not load location with following site codes: "
                                             f"{', '.join(missing_site_codes)}")

        self.new_locations = list(SQLLocation.active_objects.filter(domain=self.domain,
                                                                    site_code__in=self.new_site_codes))

        for old_location in self.old_locations:
            if not self._can_perform_deprecation(old_location):
                self.errors.append("%s operation: location %s with site code %s cannot be deprecated again." % (
                    self.type, old_location.name, old_location.site_code))
                valid = False

        return valid

    def _validate_location_count(self, expected, count, location_type_code):
        valid = True
        if expected == MANY and count == 1:
            self.errors.append("%s operation: Got only one %s location." % (self.type, location_type_code))
            valid = False
        elif expected == ONE and count > 1:
            self.errors.append("%s operation: Got %s %s location." % (self.type, count, location_type_code))
            valid = False
        return valid

    @staticmethod
    def _can_perform_deprecation(location):
        if location.metadata.get(DEPRECATED_VIA) and location.metadata.get(DEPRECATED_VIA) != EXTRACT_OPERATION:
            return False
        return True

    @abstractmethod
    def perform(self):
        raise NotImplementedError


class MergeOperation(BaseOperation):
    type = MERGE_OPERATION
    expected_old_locations = MANY

    def perform(self):
        from custom.icds.location_reassignment.tasks import reassign_cases_for_owner
        timestamp = datetime.utcnow()
        new_location = self.new_locations[0]
        for old_location in self.old_locations:
            old_location.metadata[DEPRECATED_TO] = f"{new_location.location_id}"
            old_location.metadata[DEPRECATED_AT] = timestamp
            old_location.metadata[DEPRECATED_VIA] = self.type
            old_location.is_archived = True
            old_location.archived_on = timestamp
            old_location.save()

        new_location.metadata[DEPRECATES] = ",".join([l.location_id for l in self.old_locations])
        new_location.metadata[DEPRECATES_AT] = timestamp
        new_location.metadata[DEPRECATES_VIA] = self.type
        new_location.save()
        for old_location in self.old_locations:
            reassign_cases_for_owner.delay(self.domain, old_location.location_id, new_location.location_id,
                                           timestamp)


class SplitOperation(BaseOperation):
    type = SPLIT_OPERATION
    expected_new_locations = MANY

    def perform(self):
        timestamp = datetime.utcnow()
        old_location = self.old_locations[0]
        old_location.metadata[DEPRECATED_TO] = ",".join([l.location_id for l in self.new_locations])
        old_location.metadata[DEPRECATED_AT] = timestamp
        old_location.metadata[DEPRECATED_VIA] = self.type
        old_location.is_archived = True
        old_location.archived_on = timestamp
        old_location.save()

        for new_location in self.new_locations:
            new_location.metadata[DEPRECATES] = f"{old_location.location_id}"
            new_location.metadata[DEPRECATES_AT] = timestamp
            new_location.metadata[DEPRECATES_VIA] = self.type
            new_location.save()


class ExtractOperation(BaseOperation):
    type = EXTRACT_OPERATION
    deactivates_old_users = False
    archives_old_locations = False

    def perform(self):
        timestamp = datetime.utcnow()
        old_location = self.old_locations[0]
        new_location = self.new_locations[0]
        old_location.metadata[DEPRECATED_TO] = f"{new_location.location_id}"
        old_location.metadata[DEPRECATED_AT] = timestamp
        old_location.metadata[DEPRECATED_VIA] = self.type
        old_location.save()

        new_location.metadata[DEPRECATES] = f"{old_location.location_id}"
        new_location.metadata[DEPRECATES_AT] = timestamp
        new_location.metadata[DEPRECATES_VIA] = self.type
        new_location.save()


class MoveOperation(BaseOperation):
    type = MOVE_OPERATION

    def perform(self):
        from custom.icds.location_reassignment.tasks import reassign_cases_for_owner
        timestamp = datetime.utcnow()
        old_location = self.old_locations[0]
        new_location = self.new_locations[0]
        old_location.metadata[DEPRECATED_TO] = ",".join([new_location.location_id])
        old_location.metadata[DEPRECATED_AT] = timestamp
        old_location.metadata[DEPRECATED_VIA] = self.type
        old_location.is_archived = True
        old_location.archived_on = timestamp
        old_location.save()

        new_location.metadata[DEPRECATES] = f"{old_location.location_id}"
        new_location.metadata[DEPRECATES_AT] = timestamp
        new_location.metadata[DEPRECATES_VIA] = self.type
        new_location.save()
        reassign_cases_for_owner.delay(self.domain, old_location.location_id, new_location.location_id,
                                       timestamp)
