from collections import defaultdict

from custom.icds.location_rationalization.const import (
    EXTRACT_TRANSITION,
    MERGE_TRANSITION,
    MOVE_TRANSITION,
    SPLIT_TRANSITION,
    TRANSITION_COLUMN_NAME,
    VALID_TRANSITIONS,
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
        # mapping each location code to the type of transition requested for it
        self.requested_transitions = {}
        self.errors = []
        # location types should be in reverse order of hierarchy
        self.location_types = location_types
        self.transitions = {location_type: {
            MERGE_TRANSITION: defaultdict(list),
            SPLIT_TRANSITION: defaultdict(list),
            MOVE_TRANSITION: {},
            EXTRACT_TRANSITION: {},
        } for location_type in location_types}

    def parse(self):
        for row in self.worksheet:
            transition = row.get(TRANSITION_COLUMN_NAME)
            if not transition:
                continue
            if transition not in VALID_TRANSITIONS:
                self.errors.append("Invalid Transition %s" % transition)
            self._parse_row(row)
        return self.transitions, self.errors

    def _parse_row(self, row):
        transition = row.get(TRANSITION_COLUMN_NAME)
        for location_type in self.location_types:
            # ToDo: Ensure we already get string values so that 0s in beginning are not trimmed
            old_value = str(row.get(f'old_{location_type}'))
            new_value = str(row.get(f'new_{location_type}'))
            if not old_value or not new_value:
                self.errors.append("Missing location code for %s, got old: '%s' and new: '%s'" % (
                    transition, old_value, new_value
                ))
                continue
            # if no change in a lower level location, assume none above it
            if old_value == new_value:
                continue
            if self._invalid_row(transition, old_value, new_value):
                continue
            self._note_transition(transition, location_type, new_value, old_value)

    def _invalid_row(self, transition, old_value, new_value):
        invalid = False
        if old_value in self.requested_transitions:
            if self.requested_transitions.get(old_value) != transition:
                self.errors.append("Multiple transitions for %s, %s and %s" % (
                    old_value, self.requested_transitions.get(old_value), transition))
                invalid = True
        if new_value in self.requested_transitions:
            if self.requested_transitions.get(new_value) != transition:
                self.errors.append("Multiple transitions for %s, %s and %s" % (
                    new_value, self.requested_transitions.get(new_value), transition))
                invalid = True
        return invalid

    def _note_transition(self, transition, location_type, new_value, old_value):
        if transition == MERGE_TRANSITION:
            self.transitions[location_type][transition][new_value].append(old_value)
        elif transition == SPLIT_TRANSITION:
            self.transitions[location_type][transition][old_value].append(new_value)
        elif transition == MOVE_TRANSITION:
            self.transitions[location_type][transition][new_value] = old_value
        elif transition == EXTRACT_TRANSITION:
            self.transitions[location_type][transition][new_value] = old_value
        self.requested_transitions[old_value] = transition
        self.requested_transitions[new_value] = transition
