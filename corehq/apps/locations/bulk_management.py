"""
Bulk rearrange locations.

This includes support for changing location types, changing locations' parents,
deleting things, and so on.  See the spec doc for specifics:
https://docs.google.com/document/d/1gZFPP8yXjPazaJDP9EmFORi88R-jSytH6TTgMxTGQSk/
"""
import copy
import itertools
from collections import Counter, defaultdict

from django.db import transaction
from django.utils.translation import ugettext as _

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location, SQLLocation, LocationType
from .tree_utils import BadParentError, CycleError, assert_no_cycles, expansion_validators
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
    """
    A representation of location type excel row
    """
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

    def is_new(self, old_collection):
        return self.code not in old_collection.types_by_code

    def _needs_save(self, old_collection):
        # returns True if this should be saved
        if self.is_new(old_collection) or self.do_delete:
            return True

        old_version = old_collection.types_by_code[self.code]
        if (old_version.parent_type and old_version.parent_type.code != self.parent_code):
            return True

        for attr in ['name', 'code', 'shares_cases'
                     'view_descendants', 'expand_from', 'sync_to']:
            if getattr(old_version, attr, None) != getattr(self, attr, None):
                return True
        return False

    def _as_db_object(self, old_collection, parent_type, domain):
        # returns a SQLLocation version of the stub
        if self.is_new(old_collection):
            obj = LocationType(domain=domain)
        else:
            obj = copy.copy(old_collection.types_by_code[self.code])
        return obj

    def save_if_needed(self, old_collection, parent_type, domain):
        db_object = self._as_db_object(old_collection, parent_type, domain)
        if self.do_delete:
            db_object.delete()
            return None

        db_object.parent_type = parent_type
        # todo, expand_from and sync_to
        for attr in ['name', 'code', 'shares_cases'
                     'view_descendants']:
            setattr(db_object, attr, getattr(self, attr, None))

        if self._needs_save(old_collection):
            db_object.save()

        return db_object


class LocationStub(object):
    """
    A representation of location excel row
    """
    titles = LOCATION_SHEET_HEADERS

    def __init__(self, name, site_code, location_type, parent_code, location_id,
                 do_delete, external_id, latitude, longitude, index):
        self.name = name
        self.site_code = site_code
        self.location_type = location_type
        self.location_id = location_id
        self.parent_code = parent_code or ROOT_LOCATION_TYPE
        self.latitude = latitude or None
        self.longitude = longitude or None
        self.do_delete = do_delete
        self.external_id = external_id
        self.index = index
        self.is_new = False
        if not self.location_id and not self.site_code:
            raise LocationExcelSheetError(
                _(u"Location in sheet '{}', at row '{}' doesn't contain both location_id and site_code")
                .format(self.location_type, self.index)
            )

    @classmethod
    def from_excel_row(cls, row, index, location_type):
        name = row.get(cls.titles['name'])
        site_code = row.get(cls.titles['site_code'])
        location_type = location_type
        location_id = row.get(cls.titles['location_id'])
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
            # Both can't be empty, this should have already been caught in initialization
            raise Exception(
                _(u"Location in sheet '{}', at row '{}' doesn't contain both location_id and site_code")
                .format(self.location_type, self.index)
            )

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

    def _needs_save(self, old_collection):
        # returns True if this should be saved
        # assumes self.autoset_location_id_or_site_code is already called
        if self.is_new or self.do_delete:
            return True

        old_version = old_collection.locations_by_id[self.location_id]

        if (self.location_type != old_version.location_type.code or
           (old_version.parent and self.parent_code != old_version.parent.site_code)):
            return True

        for attr in ['name', 'site_code', 'latitude', 'longitude', 'external_id']:
            if getattr(old_version, attr, None) != getattr(self, attr, None):
                return True
        return False

    def _as_db_object(self, old_collection, domain):
        # returns a SQLLocation version of the stub
        if self.is_new:
            obj = SQLLocation(domain=domain)
        else:
            obj = copy.copy(old_collection.locations_by_id[self.location_id])

        return obj

    def save_if_needed(self, old_collection, parent_location, domain, location_type):

        db_object = self._as_db_object(old_collection, domain)

        if self.do_delete:
            db_object.delete()
            return None

        db_object.parent = parent_location
        db_object.location_type = location_type
        for attr in ['name', 'site_code',
                     'latitude', 'longitude', 'external_id']:
            setattr(db_object, attr, getattr(self, attr, None))

        db_object.parent = parent_location
        if self._needs_save(old_collection):
            db_object.save()

        return db_object


class LocationCollection(object):
    """
    Simple wrapper to lookup types and locations in a domain
    """
    def __init__(self, domain_obj):
        self.types = domain_obj.location_types
        locations = [
            [l.sql_location for l in Location.filter_by_type(domain_obj.name, loc_type.name)]
            for loc_type in self.types
        ]
        self.locations = list(itertools.chain(*locations))

    @property
    @memoized
    def locations_by_id(self):
        return {l.location_id: l for l in self.locations}

    @property
    @memoized
    def locations_by_site_code(self):
        return {l.site_code: l for l in self.locations}

    @property
    @memoized
    def types_by_code(self):
        return {lt.code: lt for lt in self.types}


class LocationExcelValidator(object):
    types_sheet_title = "types"

    def __init__(self, excel_importer):
        self.excel_importer = excel_importer

    def validate_and_parse_stubs_from_excel(self):
        # This validates format of the uploaded excel file and coverts excel rows into stubs
        sheets_by_title = {ws.title: ws for ws in self.excel_importer.worksheets}

        # excel file should contain 'types' sheet
        if self.types_sheet_title not in sheets_by_title:
            raise LocationExcelSheetError("'types' sheet is required")

        # 'types' sheet should have correct headers
        type_sheet_reader = sheets_by_title[self.types_sheet_title]
        if set(type_sheet_reader.headers) != set(LOCATION_TYPE_SHEET_HEADERS.values()):
            raise LocationExcelSheetError(
                _(u"'types' sheet should contain exactly '{}' as the sheet headers")
                .format(", ".join(LOCATION_TYPE_SHEET_HEADERS.values()))
            )

        # all listed types should have a corresponding locations sheet
        type_stubs = self._get_types(type_sheet_reader)
        expected_sheet_names = [lt.code for lt in type_stubs] + ['types']
        actual_sheet_names = sheets_by_title.keys()
        missing_sheet_names = set(expected_sheet_names) - set(actual_sheet_names)
        if missing_sheet_names:
            raise LocationExcelSheetError(
                _(u"Location sheets do not exist for the location types '{}' - "
                  "All types listed in 'types' sheet should have a location sheet")
                .format(", ".join(missing_sheet_names))
            )

        # all locations sheets should have correct headers
        location_stubs = []
        for sheet_name, sheet_reader in sheets_by_title.items():
            if sheet_name != self.types_sheet_title:
                if set(sheet_reader.headers) != set(LOCATION_SHEET_HEADERS.values()):
                    raise LocationExcelSheetError(
                        _(u"Locations sheet with title '{}' should contain exactly '{}' as the sheet headers")
                        .format(sheet_name, ", ".join(LOCATION_SHEET_HEADERS.values()))
                    )
                location_stubs.extend(self._get_locations(sheet_reader, sheet_name))
        return type_stubs, location_stubs

    def _get_types(self, rows):
        # takes raw excel row dicts and converts them to list of LocationTypeStub objects
        return [
            LocationTypeStub.from_excel_row(row, index)
            for index, row in enumerate(rows)
        ]

    def _get_locations(self, rows, location_type):
        # takes raw excel row dicts and converts them to list of LocationStub objects
        return [
            LocationStub.from_excel_row(row, index, location_type)
            for index, row in enumerate(rows)
        ]


class NewLocationImporter(object):
    """
    This takes location type and location stubs, validates data and the tree
    and saves the changes in a transaction.
    """

    def __init__(self, domain, type_rows, location_rows):
        self.domain = domain
        self.domain_obj = Domain.get_by_name(domain)
        self.type_rows = type_rows
        self.location_rows = location_rows
        self.result = LocationUploadResult()
        self.old_collection = LocationCollection(self.domain_obj)

    @classmethod
    def from_excel_importer(cls, domain, excel_importer):
        type_rows, location_rows = LocationExcelValidator(excel_importer).validate_and_parse_stubs_from_excel()
        return cls(domain, type_rows, location_rows)

    def run(self):
        tree_validator = LocationTreeValidator(self.type_rows, self.location_rows, self.old_collection)
        self.result.errors = tree_validator.errors
        self.result.warnings = tree_validator.warnings
        if self.result.errors:
            return self.result

        with transaction.atomic():
            self.commit_changes(self.type_rows, self.location_rows)

        return self.result

    def commit_changes(self, type_stubs, location_stubs):
        # assumes all valdiations are done, just saves them
        # ToDo Combine calls in same level into one DB call
        type_stubs_by_parent_code = defaultdict(list)
        for lt in type_stubs:
            type_stubs_by_parent_code[lt.parent_code].append(lt)

        types_by_code = {}

        def create_child_types(parent_type):
            if parent_type == ROOT_LOCATION_TYPE:
                parent_code = ROOT_LOCATION_TYPE
                parent_type = None
            else:
                parent_code = parent_type.code
            child_stubs = type_stubs_by_parent_code[parent_code]

            for type_stub in child_stubs:
                type_object = type_stub.save_if_needed(self.old_collection, parent_type, self.domain)
                if type_object:
                    # check if type_stub was deleted, in which case type_object would be None
                    types_by_code[type_object.code] = type_object
                    create_child_types(type_object)

        create_child_types(ROOT_LOCATION_TYPE)

        location_stubs_by_parent_code = defaultdict(list)
        for l in location_stubs:
            if l.do_delete:
                l._as_db_object(self.old_collection, self.domain)
            location_stubs_by_parent_code[l.parent_code].append(l)

        def create_child_locations(parent_location):
            if parent_location == ROOT_LOCATION_TYPE:
                parent_code = ROOT_LOCATION_TYPE
                parent_location = None
            else:
                parent_code = parent_location.site_code
            child_stubs = location_stubs_by_parent_code[parent_code]

            for child in child_stubs:
                lt = types_by_code.get(child.location_type)
                child_object = child.save_if_needed(
                    self.old_collection,
                    parent_location,
                    self.domain,
                    lt
                )
                if child_object:
                    # check if child was deleted, in which case child_object would be None
                    create_child_locations(child_object)
        create_child_locations(ROOT_LOCATION_TYPE)


class LocationTreeValidator(object):
    """
    Validates the given type and location stubs
    """
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
        for loc in self.all_listed_locations:
            loc.autoset_location_id_or_site_code(self.old_collection)

        self.types_by_code = {lt.code: lt for lt in self.location_types}
        self.locations_by_code = {l.site_code: l for l in self.locations}

    @property
    def warnings(self):
        # should be called after errors are found
        def bad_deletes():
            return [
                _(u"Location deletion in sheet '{type}', row '{i}' is ignored, "
                  "as the location does not exist")
                .format(type=loc.location_type, i=loc.index)
                for loc in self.all_listed_locations
                if loc.is_new and loc.do_delete
            ]
        return bad_deletes()

    @property
    @memoized
    def errors(self):
        # We want to find as many errors as possible up front, but some high
        # level errors make it unrealistic to keep validating

        location_row_errors = (self._site_code_and_location_id_missing() +
                               self._check_unknown_location_ids())

        unknown_or_missing_errors = []
        if self.old_collection:
            # all old types/locations should be listed in excel
            unknown_or_missing_errors = (self._check_unlisted_type_codes() +
                                         self._check_unlisted_location_ids())

        uniqueness_errors = (self._check_unique_type_codes() +
                             self._check_unique_location_codes() +
                             self._check_unique_location_ids())

        basic_errors = uniqueness_errors + unknown_or_missing_errors + location_row_errors

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
            _(u"Location in sheet '{type}' at index {index} has no site_code and location_id - "
              "at least one of them should be listed")
            .format(type=l.location_type, index=l.index)
            for l in self.all_listed_locations
            if not l.site_code and not l.location_id
        ]

    @memoized
    def _check_unique_type_codes(self):
        counts = Counter(lt.code for lt in self.all_listed_types).items()
        return [
            _(u"Location type code '{}' is used {} times - they should be unique")
            .format(code, count)
            for code, count in counts if count > 1
        ]

    @memoized
    def _check_unique_location_codes(self):
        counts = Counter(l.site_code for l in self.all_listed_locations).items()
        return [
            _(u"Location site_code '{}' is used {} times - they should be unique")
            .format(code, count)
            for code, count in counts if count > 1
        ]

    @memoized
    def _check_unique_location_ids(self):
        counts = Counter(l.location_id for l in self.all_listed_locations if l.location_id).items()
        return [
            _(u"Location location_id '{}' is listed {} times - they should be listed once")
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
            _(u"Location type code '{}' is not listed in the excel. All types should be listed")
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
            _(u"Location '{name} (id {id})' is not listed in the excel. All locations should be listed")
            .format(name=old[location_id].name, id=location_id)
            for location_id in unlisted
        ]

    @memoized
    def _check_unknown_location_ids(self):
        # count location_ids listed in the excel that are not found in the domain
        if not self.old_collection:
            return []
        old = self.old_collection.locations_by_id
        listed = {l.location_id: l for l in self.all_listed_locations if l.location_id}
        unknown = set(listed.keys()) - set(old.keys())

        return [
            _(u"Location 'id: {id}' is not found in your domain. It's listed in the sheet {type} at row {index}")
            .format(id=l_id, type=listed[l_id].location_type, index=listed[l_id].index)
            for l_id in unknown
        ]

    @memoized
    def _validate_types_tree(self):
        type_pairs = [(lt.code, lt.parent_code) for lt in self.location_types]
        try:
            assert_no_cycles(type_pairs)
        except BadParentError as e:
            return [
                _(u"Location Type '{}' refers to a parent which doesn't exist").format(code)
                for code in e.affected_nodes
            ]
        except CycleError as e:
            return [
                _(u"Location Type '{}' has a parentage that loops").format(code)
                for code in e.affected_nodes
            ]

        allowed_from_codes, allowed_to_codes = expansion_validators(type_pairs)
        errors = []
        for lt in self.location_types:
            if lt.expand_from and lt.expand_from not in allowed_from_codes(lt.code):
                errors.append(
                    _(u"'{}' can't have '{}' as 'Expand From', valid options are '{}'")
                    .format(lt.code, lt.expand_from, allowed_from_codes)
                )

            if lt.sync_to and lt.sync_to not in allowed_to_codes(lt.code):
                errors.append(
                    _(u"'{}' can't have '{}' as 'Sync To', valid options are '{}'")
                    .format(lt.code, lt.sync_to, allowed_to_codes)
                )

        return errors

    @memoized
    def _validate_location_tree(self):
        errors = []

        def _validate_location(location):
            loc_type = self.types_by_code.get(location.location_type)
            if not loc_type:
                return _(u"Location '{}' in sheet points to a to be deleted location-type '{}'").format(
                    location.site_code, location.location_type)

            parent = self.locations_by_code.get(location.parent_code)
            if loc_type.parent_code == ROOT_LOCATION_TYPE:
                if parent:
                    return _(u"Location '{}' is a '{}' and should not have a parent").format(
                        location.site_code, location.location_type)
                else:
                    return
            else:
                if not parent:
                    return _(u"Location '{}' does not have a parent set or its parent is being deleted").format(
                        location.site_code)
            correct_parent_type = loc_type.parent_code
            if parent == ROOT_LOCATION_TYPE or parent.location_type != correct_parent_type:
                return _(u"Location '{}' is a '{}', so it should have a parent that is a '{}'").format(
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
                        (_(u"There are {} locations with the name '{}' under the parent '{}'")
                         .format(count, name, parent))
                    )
        return errors


def new_locations_import(domain, excel_importer):
    try:
        importer = NewLocationImporter.from_excel_importer(domain, excel_importer)
    except LocationExcelSheetError, e:
        result = LocationUploadResult()
        result.errors = [str(e)]
        return result

    result = importer.run()
    return result
