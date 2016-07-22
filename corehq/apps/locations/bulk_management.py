"""
Bulk rearrange locations.

This includes support for changing location types, changing locations' parents,
deleting things, and so on.  See the spec doc for specifics:
https://docs.google.com/document/d/1gZFPP8yXjPazaJDP9EmFORi88R-jSytH6TTgMxTGQSk/
"""
from collections import Counter, defaultdict

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location
from .tree_utils import BadParentError, CycleError, assert_no_cycles
from .const import LOCATION_SHEET_HEADERS, LOCATION_TYPE_SHEET_HEADERS, ROOT_LOCATION_TYPE


class LocationExcelSheetError(Exception):
    pass


class LocationUploadResult(object):
    def __init__(self):
        self.messages = []
        self.errors = []
        self.warnings = []

    @property
    def success(self):
        return not self.errors


class LocationTypeStub(object):
    titles = LOCATION_TYPE_SHEET_HEADERS

    def __init__(self, name, code, parent_code, do_delete, shares_cases,
                 view_descendants, expand_from, sync_to, index):
        self.name = name
        self.code = code
        # if parent_code is '', it must be top location type
        self.parent_code = parent_code or ROOT_LOCATION_TYPE
        self.do_delete = do_delete
        self.shares_cases = shares_cases
        self.view_descendants = view_descendants
        self.expand_from = expand_from
        self.sync_to = sync_to
        self.index = index

    @classmethod
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
        self.is_new = False
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

    def autoset_location_id_or_site_code(self, old_collection):
        # if one of location_id/site_code are missing, lookup for the other in
        # location_id/site_code pairs autoset the other if found.
        # self.is_new is set to True if new location

        if self.location_id and self.site_code:
            return

        if not self.location_id and not self.site_code:
            # Both can't be empty, this should have already been caught
            raise Exception

        old_locations_by_id = old_collection.locations_by_id
        old_locations_by_site_code = old_collection.locations_by_site_code
        # must be an existing location specified with just location_id
        if not self.site_code:
            if self.location_id in old_locations_by_id:
                self.site_code = old_locations_by_id[self.location_id].site_code
            else:
                # Unknown location_id, this should have already been caught
                raise Exception
        elif not self.location_id:
            if self.site_code in old_locations_by_site_code:
                # existing location specified with just site_code
                self.location_id = old_locations_by_site_code[self.site_code].location_id
            else:
                # must be a new location
                self.is_new = True


class LocationCollection(object):
    def __init__(self, domain_obj):
        self.types = domain_obj.location_types
        self.locations = [
            Location.filter_by_type(self.domain, loc_type.name)
            for loc_type in self.types
        ]

    @property
    def locations_by_id(self):
        return {l.location_id: l for l in self.locations}

    @property
    def locations_by_site_code(self):
        return {l.site_code: l for l in self.locations}


class NewLocationImporter(object):

    types_sheet_title = "types"
    locations_sheet_title = "locations"

    def __init__(self, domain, excel_importer, location_rows=None):
        self.domain = domain
        self.domain_obj = Domain.get_by_name(domain)
        self.excel_importer = excel_importer
        self.sheets_by_title = self._validate_and_index_sheets()
        self.result = LocationUploadResult()
        self.old_collection = LocationCollection(self.domain_obj)

    def _validate_and_index_sheets(self):
        # validate excel format/headers
        sheets_by_title = {ws.title: ws for ws in self.excel_importer.worksheets}
        # Todo handle multiple sheets with same name
        if self.types_sheet_title not in self.sheets_by_title:
            raise LocationExcelSheetError("'types' sheet is required")
        if self.locations_sheet_title not in self.sheets_by_title:
            raise LocationExcelSheetError("'locations' sheet is required")
        return sheets_by_title

    def run(self):
        type_rows, location_rows = self.prepare_rows()
        if self.result.errors:
            return self.result

        tree_validator = LocationTreeValidator(type_rows, location_rows, self.old_collection)
        self.result.errors = tree_validator.errors
        if self.result.errors:
            return self.result

        self.commit_changes(type_rows, location_rows)

        return self.result

    def prepare_rows(self):
        for sheet_name, rows in self.sheets_by_title.items():
            if sheet_name == self.types_sheet_title:
                type_rows = self.prepare_types(rows)
            else:
                # must be locations sheet of type 'sheet_name'
                location_rows = self.prepare_locations(rows, sheet_name)
        return type_rows, location_rows

    def _prepare_types(self, rows):
        # takes raw excel row dicts and converts them to list of LocationTypeStub objects
        return [
            LocationTypeStub.from_excel_row(row, index)
            for index, row in enumerate(rows)
        ]

    def _prepare_locations(self, rows, location_type):
        # takes raw excel row dicts and converts them to list of LocationStub objects
        return [
            LocationStub.from_excel_row(row, index, location_type)
            for index, row in enumerate(rows)
        ]

    def commit_changes(self, type_rows, location_rows):
        # assumes all valdiations are done, just saves them
        pass


class LocationTreeValidator(object):
    def __init__(self, type_rows, location_rows, old_collection=None):

        _to_be_deleted = lambda items: filter(lambda i: i.do_delete, items)
        _not_to_be_deleted = lambda items: filter(lambda i: not i.do_delete, items)

        self.all_listed_types = type_rows
        self.location_types = _not_to_be_deleted(type_rows)
        self.types_to_be_deleted = _to_be_deleted(type_rows)

        self.all_listed_locations = location_rows
        self.locations = _not_to_be_deleted(location_rows)
        self.locations_to_be_deleted = _to_be_deleted(location_rows)

        self.old_collection = old_collection
        self.types_by_code = {lt.code: lt for lt in self.location_types}
        self.locations_by_code = {l.site_code: l for l in self.locations}

    @property
    @memoized
    def errors(self):
        # We want to find as many errors as possible up front, but some high
        # level errors make it unrealistic to keep validating

        location_row_errors = (self._site_code_and_location_id_missing() +
                               self._check_unknown_location_ids())

        if not location_row_errors:
            for loc in self.all_listed_locations:
                loc.autoset_location_id_or_site_code(self.old_collection)

        unknown_or_missing_errors = []
        if self.old_collection:
            # all old types/locations should be listed in excel
            unknown_or_missing_errors = (self._check_unlisted_type_codes() +
                                         self._check_unlisted_location_ids())

        uniqueness_errors = (self._check_unique_type_codes() +
                             self._check_unique_location_codes() +
                             self._check_unique_location_ids())

        basic_errors = uniqueness_errors + unknown_or_missing_errors

        if basic_errors:
            # it doesn't make sense to try to validate a tree when you can't
            # uniquely determine the relationships
            return basic_errors

        # Make sure the location types make sense
        type_errors = self._validate_types_tree()
        if type_errors:
            return type_errors

        # Check each location's position in the tree
        errors = self._validate_location_tree()

        # Location names must be unique among siblings
        errors.extend(self._check_location_names())
        return errors

    @memoized
    def _site_code_and_location_id_missing(self):
        return [
            "Location in sheet '{type}', index {index} has no site_code and location_id"
            .format(type=l.location_type, index=l.index)
            for l in self.all_listed_locations
        ]

    @memoized
    def _check_unique_type_codes(self):
        counts = Counter(lt.code for lt in self.all_listed_types).items()
        return [
            "Location type code '{}' is used {} times - they should be unique"
            .format(code, count)
            for code, count in counts if count > 1
        ]

    @memoized
    def _check_unique_location_codes(self):
        counts = Counter(l.site_code for l in self.all_listed_locations).items()
        return [
            "Location site_code '{}' is used {} times - they should be unique"
            .format(code, count)
            for code, count in counts if count > 1
        ]

    @memoized
    def _check_unique_location_ids(self):
        counts = Counter(l.location_id for l in self.all_listed_locations).items()
        return [
            "Location location_id '{}' is listed {} times - they should be listed once"
            .format(location_id, count)
            for location_id, count in counts if count > 1
        ]

    @memoized
    def _check_unlisted_type_codes(self):
        # count types not listed in excel but are present in the domain now
        old_codes = [lt.code for lt in self.old_collection.types]
        listed_codes = [lt.code for lt in self.all_listed_types]
        unlisted_codes = set(old_codes) - set(listed_codes)

        return [
            "Location type code '{}' is not listed in the excel. All types should be listed"
            .format(code)
            for code in unlisted_codes
        ]

    @memoized
    def _check_unlisted_location_ids(self):
        # count locations not listed in excel but are present in the domain now
        old = self.old_collection.locations_by_id
        listed = [l.location_id for l in self.all_listed_locations]
        unlisted = set(old.keys()) - set(listed)

        return [
            "Location '{name} (id {id})' is not listed in the excel. All locations should be listed"
            .format(name=old[location_id].name, id=location_id)
            for location_id in unlisted
        ]

    @memoized
    def _check_unknown_location_ids(self):
        # count location_ids listed in the excel that are not found in the domain
        old = self.old_collection.locations_by_id
        listed = {l.location_id: l for l in self.all_listed_locations if l.location_id}
        unknown = set(listed.keys()) - set(old.keys())

        return [
            "Location 'id: {id}' is not found in your domain. It's listed in the sheet {type} at row {index}"
            .format(id=l_id, type=listed[l_id].location_type, index=listed[l_id].index)
            for l_id in unknown
        ]

    @memoized
    def _validate_types_tree(self):
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

    @memoized
    def _validate_location_tree(self):
        errors = []

        def _validate_location(location):
            loc_type = self.types_by_code.get(location.location_type)
            if not loc_type:
                return "Location '{}' has an invalid type".format(location.site_code)

            parent = self.locations_by_code.get(location.parent_code)
            if loc_type.parent_code == ROOT_LOCATION_TYPE:
                if parent:
                    return "Location '{}' is a '{}' and should not have a parent".format(
                           location.site_code, location.location_type)
                else:
                    return

            correct_parent_type = loc_type.parent_code
            if parent == ROOT_LOCATION_TYPE or parent.location_type != correct_parent_type:
                return "Location '{}' is a '{}', so it should have a parent that is a '{}'".format(
                       location.site_code, location.location_type, correct_parent_type)

        for location in self.locations:
            error = _validate_location(location)
            if error:
                errors.append(error)

        return errors

    @memoized
    def _check_location_names(self):
        locs_by_parent = defaultdict(list)
        for loc in self.locations:
            locs_by_parent[loc.parent_code].append(loc)
        errors = []
        for parent, siblings in locs_by_parent.items():
            counts = Counter(l.name for l in siblings).items()
            for name, count in counts:
                if count > 1:
                    errors.append(
                        ("There are {} locations with the name '{}' under the parent '{}'"
                         .format(count, name, parent))
                    )
        return errors


def bulk_update_organization(domain, location_types, locations):
    """
    Takes the existing location types and locations on the domain and modifies
    them to produce the location_types and locations passed in.

    This is used for operations that affect a large number of locations (such
    as adding a new location type), which are challenging or impossible to do
    piecemeal.
    """
    pass
