"""
Bulk rearrange locations.

This includes support for changing location types, changing locations' parents,
deleting things, and so on.  See the spec doc for specifics:
https://docs.google.com/document/d/1gZFPP8yXjPazaJDP9EmFORi88R-jSytH6TTgMxTGQSk/
"""
from __future__ import absolute_import
from __future__ import unicode_literals
import copy
from collections import Counter, defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import string_concat, ugettext as _, ugettext_lazy

from corehq.apps.locations.util import get_location_data_model
from memoized import memoized
from dimagi.utils.chunked import chunked

from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation, LocationType
from .tree_utils import BadParentError, CycleError, assert_no_cycles
from .const import LOCATION_SHEET_HEADERS, LOCATION_TYPE_SHEET_HEADERS, ROOT_LOCATION_TYPE, \
    LOCATION_SHEET_HEADERS_OPTIONAL, LOCATION_SHEET_HEADERS_BASE
import six


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
    meta_data_attrs = ['name', 'code', 'shares_cases', 'view_descendants']

    def __init__(self, name, code, parent_code, do_delete, shares_cases,
                 view_descendants, index):
        self.name = name
        self.code = code
        # if parent_code is '', it must be top location type
        self.parent_code = parent_code or ROOT_LOCATION_TYPE
        self.do_delete = do_delete
        self.shares_cases = shares_cases
        self.view_descendants = view_descendants
        self.index = index
        # These can be set by passing information of existing location data latter.
        # Whether the type already exists in domain or is new
        self.is_new = False
        # The SQL LocationType object, either an unsaved or the actual database object
        #   depending on whether 'is_new' is True or not
        self.db_object = None
        # Whether the db_object needs a SQL save, either because it's new or because some attributes
        #   are changed
        self.needs_save = False

    @classmethod
    def from_excel_row(cls, row, index):
        name = row.get(cls.titles['name'])
        code = row.get(cls.titles['code'])
        parent_code = row.get(cls.titles['parent_code'])
        do_delete = row.get(cls.titles['do_delete'], 'N').lower() in ['y', 'yes']
        shares_cases = row.get(cls.titles['shares_cases'], 'N').lower() in ['y', 'yes']
        view_descendants = row.get(cls.titles['view_descendants'], 'N').lower() in ['y', 'yes']
        index = index
        return cls(name, code, parent_code, do_delete, shares_cases,
                   view_descendants, index)

    def _is_new(self, old_collection):
        return self.code not in old_collection.types_by_code

    def lookup_old_collection_data(self, old_collection):
        # Lookup whether the type already exists in old_collection or is new. Depending on that
        # set attributes like 'is_new', 'needs_save', 'db_obect'
        self.is_new = self._is_new(old_collection)

        if self.is_new:
            self.db_object = LocationType(domain=old_collection.domain_name)
        else:
            self.db_object = copy.copy(old_collection.types_by_code[self.code])

        self.needs_save = self._needs_save()

        for attr in self.meta_data_attrs:
            setattr(self.db_object, attr, getattr(self, attr, None))

    def _needs_save(self):
        # returns True if this should be saved
        if self.is_new or self.do_delete:
            return True

        old_version = self.db_object
        # check if any attributes are being updated
        for attr in self.meta_data_attrs:
            if getattr(old_version, attr, None) != getattr(self, attr, None):
                return True

        # check if the parent is being updated
        old_parent_code = old_version.parent_type.code if old_version.parent_type else ROOT_LOCATION_TYPE
        if old_parent_code != self.parent_code:
            return True
        return False


class LocationStub(object):
    """
    A representation of location excel row
    """
    titles = LOCATION_SHEET_HEADERS
    NOT_PROVIDED = 'NOT_PROVIDED_IN_EXCEL'
    meta_data_attrs = ['name', 'site_code', 'latitude', 'longitude', 'external_id']

    def __init__(self, name, site_code, location_type, parent_code, location_id,
                 do_delete, external_id, latitude, longitude, custom_data, index,
                 location_data_model, delete_uncategorized_data=False):
        self.name = name
        self.site_code = (str(site_code) if isinstance(site_code, int) else site_code).lower()
        self.location_type = location_type
        self.location_id = location_id
        self.parent_code = (str(parent_code) if isinstance(parent_code, int) else parent_code).lower() or ROOT_LOCATION_TYPE
        self.latitude = latitude or None
        self.longitude = longitude or None
        self.do_delete = do_delete
        self.external_id = str(external_id) if isinstance(external_id, int) else external_id
        self.index = index
        self.custom_data = custom_data
        if custom_data != self.NOT_PROVIDED:
            self.custom_data = {key: six.text_type(value) for key, value in custom_data.items()}
        self.delete_uncategorized_data = delete_uncategorized_data
        if not self.location_id and not self.site_code:
            raise LocationExcelSheetError(
                _("Location in sheet '{}', at row '{}' doesn't contain either location_id or site_code")
                .format(self.location_type, self.index)
            )
        # Whether the location already exists in domain or is new
        self.is_new = False
        # The SQLLocation object, either an unsaved or the actual database object
        #   depending on whether 'is_new' is True or not
        self.db_object = None
        # Whether the db_object needs a SQL save, either because it's new or because some attributes
        #   are changed
        self.needs_save = False
        self.moved_to_root = False
        self.data_model = location_data_model

    @classmethod
    def from_excel_row(cls, row, index, location_type, data_model):
        name = row.get(cls.titles['name'])
        site_code = row.get(cls.titles['site_code'])
        location_type = location_type
        location_id = row.get(cls.titles['location_id'])
        parent_code = row.get(cls.titles['parent_code'])
        latitude = row.get(cls.titles['latitude'])
        longitude = row.get(cls.titles['longitude'])
        do_delete = row.get(cls.titles['do_delete'], 'N').lower() in ['y', 'yes']
        external_id = row.get(cls.titles['external_id'])

        def _optional_attr(attr):
            if cls.titles[attr] in row:
                val = row.get(cls.titles[attr])
                if type(val) == dict and '' in val:
                    # when excel header is 'data: ', the value is parsed as {'': ''}, but it should be {}
                    val.pop('')
                return val
            else:
                return cls.NOT_PROVIDED

        custom_data = _optional_attr('custom_data')
        delete_uncategorized_data = row.get(cls.titles['delete_uncategorized_data'], 'N').lower() in ['y', 'yes']
        index = index
        stub = cls(name, site_code, location_type, parent_code, location_id,
                   do_delete, external_id, latitude, longitude, custom_data, index,
                   data_model, delete_uncategorized_data)
        return stub

    def lookup_old_collection_data(self, old_collection):
        # Lookup whether the location already exists in old_collection or is new.
        #   Depending on that set attributes like 'is_new', 'needs_save', 'db_obect'
        self.autoset_location_id_or_site_code(old_collection)

        if self.is_new:
            self.db_object = SQLLocation(domain=old_collection.domain_name)
        else:
            self.db_object = copy.copy(old_collection.locations_by_id[self.location_id])

        self.needs_save = self._needs_save()
        self.moved_to_root = self._moved_to_root()

        for attr in self.meta_data_attrs:
            setattr(self.db_object, attr, getattr(self, attr, None))
        self.db_object.metadata = self.custom_location_data

    @property
    @memoized
    def custom_location_data(self):
        # This just compiles the custom location data, the validation is done in _custom_data_errors()
        db_meta = copy.copy(self.db_object.metadata)
        data_provided = self.custom_data != self.NOT_PROVIDED
        if data_provided:
            metadata = self.custom_data
        else:
            metadata = db_meta

        if self.delete_uncategorized_data:
            metadata, unknown = self.data_model.get_model_and_uncategorized(metadata)
        else:
            if data_provided:
                # add back uncategorized data to new metadata
                known, unknown = self.data_model.get_model_and_uncategorized(db_meta)
                metadata.update(unknown)

        return metadata

    def autoset_location_id_or_site_code(self, old_collection):
        # if one of location_id/site_code are missing, lookup for the other in
        # location_id/site_code pairs autoset the other if found.
        # self.is_new is set to True if new location

        if self.location_id and self.site_code:
            return

        # Both can't be empty, this should have already been caught in initialization
        assert self.location_id or self.site_code

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

    def _needs_save(self):
        if self.is_new or self.do_delete:
            return True

        old_version = self.db_object
        # check if any attributes are being updated
        for attr in self.meta_data_attrs:
            old_value = getattr(old_version, attr, None)
            new_value = getattr(self, attr, None)
            if (old_value or new_value) and old_value != new_value:
                return True

        # check if custom location data is being updated
        if self.custom_location_data != old_version.metadata:
            return True

        # check if any foreign-key refs are being updated
        if (self.location_type != old_version.location_type.code):
            return True

        old_parent = old_version.parent.site_code if old_version.parent else ROOT_LOCATION_TYPE
        if old_parent != self.parent_code:
            return True

        return False

    def _moved_to_root(self):
        old_parent = self.db_object.parent.site_code if self.db_object.parent else ROOT_LOCATION_TYPE
        if not self.is_new and self.parent_code == ROOT_LOCATION_TYPE and old_parent != ROOT_LOCATION_TYPE:
            return True
        return False


class LocationCollection(object):
    """
    Simple wrapper to lookup types and locations in a domain
    """
    def __init__(self, domain_obj):
        self.domain_name = domain_obj.name
        self.types = domain_obj.location_types
        self.locations = list(SQLLocation.objects.filter(domain=self.domain_name, is_archived=False))

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
    def locations_by_parent_code(self):
        locs_by_parent = defaultdict(list)
        for loc in self.locations:
            parent_code = loc.parent.site_code if loc.parent else ''
            locs_by_parent[parent_code].append(loc)
        return locs_by_parent

    @property
    @memoized
    def types_by_code(self):
        return {lt.code: lt for lt in self.types}

    @property
    @memoized
    def custom_data_validator(self):
        from .views import LocationFieldsView
        return LocationFieldsView.get_validator(self.domain_name)


class LocationExcelValidator(object):
    types_sheet_title = "types"

    def __init__(self, domain, excel_importer):
        self.domain = domain
        self.excel_importer = excel_importer
        self.data_model = get_location_data_model(self.domain)

    def validate_and_parse_stubs_from_excel(self):
        # This validates format of the uploaded excel file and coverts excel rows into stubs
        sheets_by_title = {ws.title: ws for ws in self.excel_importer.worksheets}

        # excel file should contain 'types' sheet
        if self.types_sheet_title not in sheets_by_title:
            raise LocationExcelSheetError("'types' sheet is required")

        # 'types' sheet should have correct headers
        type_sheet_reader = sheets_by_title[self.types_sheet_title]
        actual = set(type_sheet_reader.headers)
        expected = set(LOCATION_TYPE_SHEET_HEADERS.values())
        if actual != expected:
            message = ugettext_lazy("'types' sheet should contain exactly '{expected}' as the sheet headers. "
                                    "'{missing}' are missing")
            if actual - expected:
                message = string_concat(message, ugettext_lazy(" '{extra}' are not recognized"))
            raise LocationExcelSheetError(message.format(
                expected=", ".join(expected),
                missing=", ".join(expected - actual),
                extra=", ".join(actual - expected),
            ))

        type_stubs = self._get_types(type_sheet_reader)

        # all locations sheets should have correct headers
        location_stubs = []
        optional_headers = list(LOCATION_SHEET_HEADERS_OPTIONAL.values())
        for sheet_name, sheet_reader in sheets_by_title.items():
            if sheet_name != self.types_sheet_title:
                actual = set(sheet_reader.fieldnames) - set(optional_headers)
                expected = set(LOCATION_SHEET_HEADERS_BASE.values())
                if actual != expected:
                    raise LocationExcelSheetError(
                        _("Locations sheet with title '{name}' should contain exactly '{expected}' "
                          "as the sheet headers. '{missing}' are missing")
                        .format(
                            name=sheet_name,
                            expected=", ".join(expected),
                            missing=", ".join(expected - actual))
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
            LocationStub.from_excel_row(row, index, location_type, self.data_model)
            for index, row in enumerate(rows)
        ]


class NewLocationImporter(object):
    """
    This takes location type and location stubs, validates data and the tree
    and saves the changes in a transaction.
    """

    def __init__(self, domain, type_rows, location_rows, excel_importer=None, chunk_size=100):
        self.domain = domain
        self.domain_obj = Domain.get_by_name(domain)
        self.type_rows = type_rows
        self.location_rows = location_rows
        self.result = LocationUploadResult()
        self.old_collection = LocationCollection(self.domain_obj)
        self.excel_importer = excel_importer  # excel_importer is used for providing progress feedback
        self.chunk_size = chunk_size

    @classmethod
    def from_excel_importer(cls, domain, excel_importer):
        validator = LocationExcelValidator(domain, excel_importer)
        type_rows, location_rows = validator.validate_and_parse_stubs_from_excel()
        return cls(domain, type_rows, location_rows, excel_importer)

    def run(self):
        tree_validator = LocationTreeValidator(self.type_rows, self.location_rows, self.old_collection)
        self.result.errors = tree_validator.errors
        self.result.warnings = tree_validator.warnings
        if self.result.errors:
            return self.result

        self.bulk_commit(self.type_rows, self.location_rows)

        return self.result

    def bulk_commit(self, type_stubs, location_stubs):
        for lt in type_stubs:
            lt.lookup_old_collection_data(self.old_collection)

        for loc in location_stubs:
            loc.lookup_old_collection_data(self.old_collection)

        type_objects = save_types(type_stubs, self.excel_importer)
        types_changed = any(loc_type.needs_save for loc_type in type_stubs)
        moved_to_root = any(loc.moved_to_root for loc in location_stubs)
        delay_updates = not (types_changed or moved_to_root)
        save_locations(location_stubs, type_objects, self.domain,
                       delay_updates, self.excel_importer, self.chunk_size)
        # Since we updated LocationType objects in bulk, some of the post-save logic
        #   that occurs inside LocationType.save needs to be explicitly called here
        for lt in type_stubs:
            if (not lt.do_delete and lt.needs_save):
                obj = type_objects[lt.code]
                if not lt.is_new:
                    # supply_points would have been synced while SQLLocation.save() already
                    obj.sync_administrative_status(sync_supply_points=False)

        update_count = lambda items: sum(l.needs_save and not l.do_delete and not l.is_new for l in items)
        delete_count = lambda items: sum(l.do_delete for l in items)
        new_count = lambda items: sum(l.is_new for l in items)
        self.result.messages.extend([
            _("Created {} new location types").format(new_count(type_stubs)),
            _("Updated {} existing location types").format(update_count(type_stubs)),
            _("Deleted {} existing location types").format(delete_count(type_stubs)),
            _("Created {} new locations").format(new_count(location_stubs)),
            _("Updated {} existing locations").format(update_count(location_stubs)),
            _("Deleted {} existing locations").format(delete_count(location_stubs)),
        ])


class LocationTreeValidator(object):
    """
    Validates the given type and location stubs
    """
    def __init__(self, type_rows, location_rows, old_collection=None):

        _to_be_deleted = lambda items: [i for i in items if i.do_delete]
        _not_to_be_deleted = lambda items: [i for i in items if not i.do_delete]

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
        self.locations_by_code = {l.site_code: l for l in self.all_listed_locations}

    @property
    def warnings(self):
        # should be called after errors are found
        def bad_deletes():
            return [
                _("Location deletion in sheet '{type}', row '{i}' is ignored, "
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
                               self._check_unknown_location_ids() + self._validate_geodata())

        unknown_or_missing_errors = []
        if self.old_collection:
            # all old types/locations should be listed in excel
            unknown_or_missing_errors = self._check_unlisted_type_codes()

        uniqueness_errors = (self._check_unique_type_codes() +
                             self._check_unique_location_codes() +
                             self._check_unique_location_ids())

        # validate custom location data
        custom_data_errors = self._custom_data_errors()

        basic_errors = uniqueness_errors + unknown_or_missing_errors + location_row_errors + \
            custom_data_errors

        if basic_errors:
            # it doesn't make sense to try to validate a tree when you can't
            # uniquely determine the relationships
            return basic_errors

        # Make sure the location types make sense
        type_errors = self._validate_types_tree()
        if type_errors:
            return type_errors

        # Check each location's position in the tree
        errors = self._validate_location_tree() + self._check_required_locations_missing()

        # Location names must be unique among siblings
        errors.extend(self._check_location_names())

        # Model field validation must pass
        errors.extend(self._check_model_validation())

        return errors

    @memoized
    def _validate_geodata(self):
        errors = []
        for l in self.all_listed_locations:
            try:
                if l.latitude:
                    float(l.latitude)
                if l.longitude:
                    float(l.longitude)
            except ValueError:
                errors.append(l)
        return [
            _("latitude/longitude 'lat-{lat}, lng-{lng}' for location in sheet '{type}' "
              "at index {index} should be valid decimal numbers.")
            .format(type=l.location_type, index=l.index, lat=l.latitude, lng=l.longitude)
            for l in errors
        ]

    @memoized
    def _check_required_locations_missing(self):
        if not self.locations_to_be_deleted or not self.old_collection:
            # skip this check if no old locations or no location to be deleted
            return []

        old_locs_by_parent = self.old_collection.locations_by_parent_code

        missing_locs = []
        listed_sites = {l.site_code for l in self.all_listed_locations}
        for loc in self.locations_to_be_deleted:
            required_locs = old_locs_by_parent[loc.site_code]
            missing = set([l.site_code for l in required_locs]) - listed_sites
            if missing:
                missing_locs.append((missing, loc))

        return [
            _("Location '{code}' in sheet '{type}' at index {index} is being deleted, so all its "
              "child locations must be present in the upload, but child locations '{locs}' are missing")
            .format(code=parent.site_code, type=parent.location_type, index=parent.index, locs=', '.join(old_locs))
            for (old_locs, parent) in missing_locs
        ]

    @memoized
    def _site_code_and_location_id_missing(self):
        return [
            _("Location in sheet '{type}' at index {index} has no site_code and location_id - "
              "at least one of them should be listed")
            .format(type=l.location_type, index=l.index)
            for l in self.all_listed_locations
            if not l.site_code and not l.location_id
        ]

    @memoized
    def _check_unique_type_codes(self):
        counts = list(Counter(lt.code for lt in self.all_listed_types).items())
        return [
            _("Location type code '{}' is used {} times - they should be unique")
            .format(code, count)
            for code, count in counts if count > 1
        ]

    @memoized
    def _check_unique_location_codes(self):
        counts = list(Counter(l.site_code for l in self.all_listed_locations).items())
        return [
            _("Location site_code '{}' is used {} times - they should be unique")
            .format(code, count)
            for code, count in counts if count > 1
        ]

    @memoized
    def _check_unique_location_ids(self):
        counts = list(Counter(l.location_id for l in self.all_listed_locations if l.location_id).items())
        return [
            _("Location location_id '{}' is listed {} times - they should be listed once")
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
            _("Location type code '{}' is not listed in the excel. All types should be listed")
            .format(code)
            for code in unlisted_codes
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
            _("Location 'id: {id}' is not found in your domain. It's listed in the sheet {type} at row {index}")
            .format(id=l_id, type=listed[l_id].location_type, index=listed[l_id].index)
            for l_id in unknown
        ]

    @memoized
    def _custom_data_errors(self):
        if not self.old_collection or not self.old_collection.custom_data_validator:
            # tests
            return []

        validator = self.old_collection.custom_data_validator

        return [
            _("Problem with custom data for location '{site_code}', in sheet '{type}', at index '{i}' - '{er}'")
            .format(site_code=l.site_code, type=l.location_type, i=l.index, er=validator(l.custom_data))
            for l in self.all_listed_locations
            if l.custom_data is not LocationStub.NOT_PROVIDED and validator(l.custom_data)
        ]

    @memoized
    def _validate_types_tree(self):
        type_pairs = [(lt.code, lt.parent_code) for lt in self.location_types]
        try:
            assert_no_cycles(type_pairs)
        except BadParentError as e:
            return [
                _("Location Type '{}' refers to a parent which doesn't exist").format(code)
                for code in e.affected_nodes
            ]
        except CycleError as e:
            return [
                _("Location Type '{}' has a parentage that loops").format(code)
                for code in e.affected_nodes
            ]

    @memoized
    def _validate_location_tree(self):
        errors = []

        def _validate_location(location):
            loc_type = self.types_by_code.get(location.location_type)
            if not loc_type:
                # if no location_type is set
                return (_(
                    "Location '{}' in sheet points to a nonexistent or to be deleted location-type '{}'")
                    .format(location.site_code, location.location_type))

            if loc_type.parent_code == ROOT_LOCATION_TYPE:
                # if top location then it shouldn't have a parent
                if location.parent_code != ROOT_LOCATION_TYPE:
                    return _("Location '{}' is a '{}' and should not have a parent").format(
                        location.site_code, location.location_type)
                else:
                    return
            else:
                # if not top location, its actual parent location type should match what it is set in excel
                parent = self.locations_by_code.get(location.parent_code)
                if not parent:
                    # check old_collection if it's not listed in current excel
                    parent = self.old_collection.locations_by_site_code.get(location.parent_code)
                    if not parent:
                        return _("Location '{}' does not have a parent set or its parent "
                                 "is being deleted").format(location.site_code)
                    else:
                        actual_parent_type = parent.location_type.code
                else:
                    actual_parent_type = parent.location_type
                    if parent.do_delete and not location.do_delete:
                        return _("Location points to a location that's being deleted")

                if actual_parent_type != loc_type.parent_code:
                    return _("Location '{}' is a '{}', so it should have a parent that is a '{}'").format(
                        location.site_code, location.location_type, loc_type.parent_code)

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
            counts = list(Counter(l.name for l in siblings).items())
            for name, count in counts:
                if count > 1:
                    errors.append(
                        (_("There are {} locations with the name '{}' under the parent '{}'")
                         .format(count, name, parent))
                    )
        return errors

    @memoized
    def _check_model_validation(self):
        errors = []
        for location in self.locations:
            location.lookup_old_collection_data(self.old_collection)  # This method sets location.db_object
            exclude_fields = ["location_type"]  # Skip foreign key validation
            if not location.db_object.location_id:
                # Don't validate location_id if its blank because SQLLocation.save() will add it
                exclude_fields.append("location_id")
            try:
                location.db_object.full_clean(exclude=exclude_fields)
            except ValidationError as e:
                for field, issues in six.iteritems(e.message_dict):
                    for issue in issues:
                        errors.append(_(
                            "Error with location in sheet '{}', at row {}. {}: {}").format(
                                location.location_type, location.index, field, issue
                        ))

        return errors


def new_locations_import(domain, excel_importer):
    try:
        importer = NewLocationImporter.from_excel_importer(domain, excel_importer)
    except LocationExcelSheetError as e:
        result = LocationUploadResult()
        result.errors = [str(e)]
        return result

    result = importer.run()
    return result


def save_types(type_stubs, excel_importer=None):
    """
    Given a list of LocationTypeStub objects, saves them to SQL as LocationType objects

    :param type_stubs: (list) list of LocationType objects with meta-data attributes and
          `needs_save`, 'is_new', 'db_object' set correctly
    :param excel_importer: Used for providing progress feedback. Disabled on None

    :returns: (dict) a dict of {object.code: object for all type objects}
    """
    #
    # This proceeds in 3 steps
    # 1. Lookup all to be deleted types and 'bulk_delete' them
    # 2. Lookup all new types and 'bulk_create' the SQL objects, but don't set ForeignKey attrs like
    #    'parent' yet
    # 3. Lookup all to be updated types. Set foreign key attrs on these and new objects, and
    #    'bulk_update' the objects

    # step 1
    to_be_deleted_types = [lt.db_object for lt in type_stubs if lt.do_delete]
    LocationType.bulk_delete(to_be_deleted_types)
    if excel_importer:
        excel_importer.add_progress(len(to_be_deleted_types))
    # step 2
    new_type_objects = LocationType.bulk_create([lt.db_object for lt in type_stubs if lt.is_new])
    if excel_importer:
        excel_importer.add_progress(len(new_type_objects))
    # step 3
    type_objects_by_code = {lt.code: lt for lt in new_type_objects}
    type_objects_by_code.update({ROOT_LOCATION_TYPE: None})
    type_objects_by_code.update({
        lt.code: lt.db_object
        for lt in type_stubs
        if not lt.is_new and not lt.do_delete
    })
    to_bulk_update = []
    for lt in type_stubs:
        if (lt.needs_save or lt.is_new) and not lt.do_delete:
            # lookup foreign key attributes from stub and set them on objects
            type_object = type_objects_by_code[lt.code]
            type_object.parent_type = type_objects_by_code[lt.parent_code]
            to_bulk_update.append(type_object)

    LocationType.bulk_update(to_bulk_update)
    if excel_importer:
        excel_importer.add_progress(len(to_bulk_update))
    all_objs_by_code = {lt.code: lt for lt in to_bulk_update}
    all_objs_by_code.update({
        lt.code: lt.db_object
        for lt in type_stubs
        if not lt.needs_save
    })
    return all_objs_by_code


def save_locations(location_stubs, types_by_code, domain, delay_updates, excel_importer=None, chunk_size=100):
    """
    :param location_stubs: (list) List of LocationStub objects with
        attributes like 'db_object', 'needs_save', 'do_delete' set
    :param types_by_code: (dict) Mapping of 'code' to LocationType SQL objects
    :param excel_importer: Used for providing progress feedback. Disabled on None

    This recursively saves tree top to bottom. Note that the bulk updates are not possible
    as the mptt.Model (inherited by SQLLocation) doesn't support bulk creation
    """

    def order_by_location_type():
        # returns locations in the order from top to bottom
        types_by_parent = defaultdict(list)
        for _type in types_by_code.values():
            key = _type.parent_type.code if _type.parent_type else ROOT_LOCATION_TYPE
            types_by_parent[key].append(_type)

        location_stubs_by_type = defaultdict(list)
        for l in location_stubs:
            location_stubs_by_type[l.location_type].append(l)

        top_to_bottom_locations = []

        def append_at_bottom(parent_type):
            top_to_bottom_locations.extend(location_stubs_by_type[parent_type.code])
            for child_type in types_by_parent[parent_type.code]:
                append_at_bottom(child_type)

        for top_type in types_by_parent[ROOT_LOCATION_TYPE]:
            append_at_bottom(top_type)

        return top_to_bottom_locations

    def _process_locations(locs_to_process, to_be_deleted):
        for loc in locs_to_process:
            if excel_importer:
                excel_importer.add_progress()
            if loc.do_delete:
                if not loc.is_new:
                    # keep track of to be deleted items to delete them in top-to-bottom order
                    to_be_deleted.append(loc.db_object)
            elif loc.needs_save:
                loc_object = loc.db_object
                loc_object.location_type = types_by_code.get(loc.location_type)
                if loc.parent_code and loc.parent_code is not ROOT_LOCATION_TYPE:
                    # refetch parent_location object so that mptt related fields are updated consistently,
                    #   since we are saving top to bottom, parent_location would not have any pending
                    #   saves, so this is the right point to refetch the object.
                    loc_object.parent = SQLLocation.objects.get(
                        domain=domain,
                        site_code__iexact=loc.parent_code
                    )
                else:
                    loc_object.parent = None
                loc.db_object.save()

    to_be_deleted = []

    top_to_bottom_locations = order_by_location_type()
    if delay_updates:
        for locs in chunked(top_to_bottom_locations, chunk_size):
            with transaction.atomic():
                with SQLLocation.objects.delay_mptt_updates():
                    _process_locations(locs, to_be_deleted)
    else:
        _process_locations(top_to_bottom_locations, to_be_deleted)

    for locs in chunked(reversed(to_be_deleted), chunk_size):
        # Deletion has to happen bottom to top, otherwise mptt complains
        #   about missing parents
        with transaction.atomic():
            with SQLLocation.objects.delay_mptt_updates():
                for l in locs:
                    l.delete()
