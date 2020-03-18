from collections import defaultdict

from corehq.apps.locations.models import SQLLocation
from custom.icds.location_rationalization.const import (
    EXTRACT_OPERATION,
    MERGE_OPERATION,
    MOVE_OPERATION,
    SPLIT_OPERATION,
    OPERATION_COLUMN_NAME,
    VALID_OPERATIONS,
)


class Parser(object):
    """
    Receives a worksheet and location types of the domain and generates an output on lines
    {
        location_type:
            'Merge': {
                'New location site code': ['Old location site code', 'Old location site code']
            },
            'Split': {
                'Old location site code': ['New location site code', 'New location site code']
            },
            'Rename': {
                'New location site code': 'Old location site code'
            },
            'Extract': {
                'New location site code': 'Old location site code'
            }
    }
    """
    def __init__(self, worksheet, location_types):
        self.worksheet = worksheet
        # mapping each location code to the type of operation requested for it
        self.requested_transitions = {}
        self.site_codes_to_be_archived = []
        self.locations_by_site_code = {}
        self.errors = []
        # location types should be in reverse order of hierarchy
        self.location_types = location_types
        self.transitions = {location_type: {
            MERGE_OPERATION: defaultdict(list),
            SPLIT_OPERATION: defaultdict(list),
            MOVE_OPERATION: {},
            EXTRACT_OPERATION: {},
        } for location_type in location_types}

    def parse(self):
        for row in self.worksheet:
            operation = row.get(OPERATION_COLUMN_NAME)
            if not operation:
                continue
            if operation not in VALID_OPERATIONS:
                self.errors.append("Invalid Operation %s" % operation)
                continue
            self._parse_row(row)
        self.validate()
        return self.transitions, self.errors

    def _parse_row(self, row):
        operation = row.get(OPERATION_COLUMN_NAME)
        for location_type in self.location_types:
            # ToDo: Ensure we already get string values so that 0s in beginning are not trimmed
            old_site_code = str(row.get(f'old_{location_type}'))
            new_site_code = str(row.get(f'new_{location_type}'))
            if not old_site_code or not new_site_code:
                self.errors.append("Missing location code for %s, got old: '%s' and new: '%s'" % (
                    operation, old_site_code, new_site_code
                ))
                continue
            # if no change in a lower level location, assume none above it
            if old_site_code == new_site_code:
                continue
            if self._invalid_row(operation, old_site_code, new_site_code):
                continue
            self._note_transition(operation, location_type, new_site_code, old_site_code)

    def _invalid_row(self, operation, old_site_code, new_site_code):
        invalid = False
        if old_site_code in self.requested_transitions:
            if self.requested_transitions.get(old_site_code) != operation:
                self.errors.append("Multiple transitions for %s, %s and %s" % (
                    old_site_code, self.requested_transitions.get(old_site_code), operation))
                invalid = True
        if new_site_code in self.requested_transitions:
            if self.requested_transitions.get(new_site_code) != operation:
                self.errors.append("Multiple transitions for %s, %s and %s" % (
                    new_site_code, self.requested_transitions.get(new_site_code), operation))
                invalid = True
        return invalid

    def _note_transition(self, operation, location_type, new_site_code, old_site_code):
        if operation == MERGE_OPERATION:
            self.transitions[location_type][operation][new_site_code].append(old_site_code)
        elif operation == SPLIT_OPERATION:
            self.transitions[location_type][operation][old_site_code].append(new_site_code)
        elif operation == MOVE_OPERATION:
            self.transitions[location_type][operation][new_site_code] = old_site_code
        elif operation == EXTRACT_OPERATION:
            self.transitions[location_type][operation][new_site_code] = old_site_code
        self.site_codes_to_be_archived.append(old_site_code)
        self.requested_transitions[old_site_code] = operation
        self.requested_transitions[new_site_code] = operation

    def validate(self):
        """
        ensure all locations getting archived, also have their descendants getting archived
        """
        site_codes_to_be_archived = set(self.site_codes_to_be_archived)
        locations_to_be_archived = SQLLocation.active_objects.filter(site_code__in=self.site_codes_to_be_archived)
        for location in locations_to_be_archived:
            descendants_sites_codes = location.get_descendants().values_list('site_code', flat=True)
            missing_site_codes = set(descendants_sites_codes) - site_codes_to_be_archived
            if missing_site_codes:
                self.errors.append("Location %s is getting archived but the following descendants are not %s" % (
                    location.location_id, ",".join(missing_site_codes)
                ))

    def process(self):
        self._load_locations()
        for location_type in list(reversed(self.location_types)):
            for operation, transitions in self.transitions[location_type].items():
                self._perform_operation(operation, transitions)

    def _load_locations(self):
        self.locations_by_site_code = {
            loc.site_code: loc
            for loc in SQLLocation.active_objects.filter(site_code__in=self.requested_transitions.keys())
        }

    def _perform_operation(self, operation, transitions):
        if operation == MERGE_OPERATION:
            for new_site_code, old_site_codes in transitions.items():
                for old_site_code in old_site_codes:
                    self._deprecate_location(old_site_code, new_site_code, operation)
        elif operation == SPLIT_OPERATION:
            for old_site_code, new_site_codes in transitions.items():
                for new_site_code in new_site_codes:
                    self._deprecate_location(old_site_code, new_site_code, operation)
        elif operation == MOVE_OPERATION:
            for new_site_code, old_site_code in transitions.items():
                self._deprecate_location(old_site_code, new_site_code, operation)
        elif operation == EXTRACT_OPERATION:
            for new_site_code, old_site_code in transitions.items():
                self._deprecate_location(old_site_code, new_site_code, operation, False)

    def _deprecate_location(self, old_site_code, new_site_code, operation, archive=True):
        old_location = self.locations_by_site_code[old_site_code]
        if new_site_code in self.locations_by_site_code:
            new_location = self.locations_by_site_code[new_site_code]
        else:
            # ToDo: Create new location if not already present and remove return
            new_location = None
            return
        old_location.deprecate_by(new_location, operation, archive=archive)
