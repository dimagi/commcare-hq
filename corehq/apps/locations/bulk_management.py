"""
Bulk rearrange locations.

This includes support for changing location types, changing locations' parents,
deleting things, and so on.  See the spec doc for specifics:
https://docs.google.com/document/d/1gZFPP8yXjPazaJDP9EmFORi88R-jSytH6TTgMxTGQSk/
"""
from collections import namedtuple, Counter, defaultdict

from dimagi.utils.decorators.memoized import memoized

from .tree_utils import BadParentError, CycleError, assert_no_cycles
from .const import LOCATION_SHEET_HEADERS, LOCATION_TYPE_SHEET_HEADERS


class LocationTypeStub(object):
    titles = LOCATION_TYPE_SHEET_HEADERS

    def __init__(self, name, code, parent_code, do_delete, shares_cases,
                 view_descendants, expand_from, sync_to, index):
        self.name = name
        self.code = code
        self.parent_code = parent_code
        self.do_delete = do_delete
        self.shares_cases = shares_cases
        self.view_descendants = view_descendants
        self.expand_from = expand_from
        self.sync_to = sync_to
        self.index = index

    def from_excel_row(cls, row, index):
        name = row.get(cls.titles['name'])
        code = row.get(cls.titles['code'])
        parent_code = row.get(cls.titles['parent_code'])
        do_delete = row.get(cls.titles['do_delete'], 'N').lower() in ['y', 'yes']
        shares_cases = row.get(cls.titles['shares_cases'], 'N').lower() in ['y', 'yes']
        view_descendants = row.get(cls.titles['view_descendants'], 'N').lower() in ['y', 'yes']
        expand_from = row.get(cls.titles['expand_from'])
        sync_to = row.get(cls.titles['sync_to'])
        index = index
        return cls(name, code, parent_code, do_delete, shares_cases,
                   view_descendants, expand_from, sync_to, index)

    def _lookup_location_id_site_code(self):
        # if one of location_id/site_code are missing, check against existing location_id/site_code
        # lookup them and set it
        if not self.location_id and not self.site_code:
            raise MissingLocationIDAndSiteCode


class LocationStub(object):
    titles = LOCATION_SHEET_HEADERS

    def __init__(self, name, site_code, location_type, parent_code, location_id,
                 do_delete, external_id, latitude, longitude, index):
        self.name = name
        self.site_code = site_code
        self.location_type = location_type
        self.location_id = location_id
        self.parent_code = parent_code
        self.latitude = latitude
        self.longitude = longitude
        self.do_delete = do_delete
        self.external_id = external_id
        self.index = index
        self.hardfail_reason = None
        self.warnings = []

    @classmethod
    def from_excel_row(cls, row, index, location_type):
        name = row.get(cls.titles['name'])
        site_code = row.get(cls.titles['site_code'])
        location_type = location_type
        location_id = row.get(cls.titles['id'])
        parent_code = row.get(cls.titles['parent_code'])
        latitude = row.get(cls.titles['latitude'])
        longitude = row.get(cls.titles['longitude'])
        do_delete = row.get(cls.titles['do_delete'], 'N').lower() in ['y', 'yes']
        external_id = row.get(cls.titles['external_id'])
        index = index
        return cls(name, site_code, location_type, parent_code, location_id,
                   do_delete, external_id, latitude, longitude, index)

    def _lookup_location_id_site_code(self):
        # if one of location_id/site_code are missing, check against existing location_id/site_code
        # lookup them and set it
        if not self.location_id and not self.site_code:
            raise MissingLocationIDAndSiteCode



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

        # Make sure the location types make sense
        type_errors = self._validate_location_types()
        if type_errors:
            return type_errors

        # Check each location's position in the tree
        errors = filter(None, [
            self._validate_location_in_tree(loc) for loc in self.locations
        ])

        # Location names must be unique among siblings
        errors.extend(self._check_location_names())
        return errors

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

    def _validate_location_in_tree(self, location):
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

    def _check_location_names(self):
        locs_by_parent = defaultdict(list)
        for loc in self.locations:
            locs_by_parent[loc.parent_code].append(loc)

        for parent, siblings in locs_by_parent.items():
            counts = Counter(l.name for l in siblings).items()
            for name, count in counts:
                if count > 1:
                    yield ("There are {} locations with the name '{}' under the parent '{}'"
                           .format(count, name, parent))


def bulk_update_organization(domain, location_types, locations):
    """
    Takes the existing location types and locations on the domain and modifies
    them to produce the location_types and locations passed in.

    This is used for operations that affect a large number of locations (such
    as adding a new location type), which are challenging or impossible to do
    piecemeal.
    """
    pass
