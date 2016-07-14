"""
Bulk rearrange locations.

This includes support for changing location types, changing locations' parents,
deleting things, and so on.  See the spec doc for specifics:
https://docs.google.com/document/d/1gZFPP8yXjPazaJDP9EmFORi88R-jSytH6TTgMxTGQSk/
"""
from collections import namedtuple, Counter

from dimagi.utils.decorators.memoized import memoized

from .tree_utils import BadParentError, CycleError, assert_no_cycles

LocationTypeStub = namedtuple(
    "LocationTypeStub",
    "name code parent_code shares_cases view_descendants"
)

LocationStub = namedtuple(
    "LocationStub",
    "name site_code location_type parent_code location_id external_id latitude longitude"
)


class LocationTreeValidator(object):
    def __init__(self, location_types, locations):
        self.location_types = location_types
        self.locations = locations
        self.types_by_code = {lt.code: lt for lt in location_types}
        self.locations_by_code = {l.site_code: l for l in locations}

    @property
    @memoized
    def errors(self):
        # We want to find as many errors as possible up front, but some high
        # level errors make it unrealistic to keep validating

        basic_errors = (self._check_unique_type_codes() +
                        self._check_unique_location_codes())
        if basic_errors:
            # it doesn't make sense to try to validate a tree when you can't
            # uniquely determine the relationships
            return basic_errors

        type_errors = self._validate_location_types()
        if type_errors:
            return type_errors

        return filter(None, [
            self._validate_location(loc) for loc in self.locations
        ])

    def _check_unique_type_codes(self):
        counts = Counter(lt.code for lt in self.location_types).items()
        return [
            "Location type code '{}' is used {} times - they should be unique"
            .format(code, count)
            for code, count in counts if count > 1
        ]

    def _check_unique_location_codes(self):
        counts = Counter(l.site_code for l in self.locations).items()
        return [
            "Location site_code '{}' is used {} times - they should be unique"
            .format(code, count)
            for code, count in counts if count > 1
        ]

    def _validate_location_types(self):
        try:
            assert_no_cycles([(lt.code, lt.parent_code) for lt in self.location_types])
        except BadParentError as e:
            return [
                "Location Type '{}' refers to a parent which doesn't exist".format(code)
                for code in e.affected_nodes
            ]
        except CycleError as e:
            return [
                "Location Type '{}' has a parentage that loops".format(code)
                for code in e.affected_nodes
            ]
        return []

    def _validate_location(self, location):
        loc_type = self.types_by_code.get(location.location_type)
        if not loc_type:
            return "Location '{}' has an invalid type".format(location.site_code)

        parent = self.locations_by_code.get(location.parent_code)

        if not loc_type.parent_code:
            # It's a top level location
            if not parent:
                return  # all good
            else:
                return ("Location '{}' is a '{}' and should not have a parent"
                        .format(location.site_code, location.location_type))

        correct_parent_type = loc_type.parent_code
        if not parent or parent.location_type != correct_parent_type:
            return ("Location '{}' is a '{}', so it should have a parent that is a '{}'"
                    .format(location.site_code, location.location_type, correct_parent_type))


def bulk_update_organization(domain, location_types, locations):
    """
    Takes the existing location types and locations on the domain and modifies
    them to produce the location_types and locations passed in.

    This is used for operations that affect a large number of locations (such
    as adding a new location type), which are challenging or impossible to do
    piecemeal.
    """
    pass
