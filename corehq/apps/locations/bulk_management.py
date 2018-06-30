"""
Bulk rearrange locations.

This includes support for changing location types, changing locations' parents,
deleting things, and so on.  See the spec doc for specifics:
https://docs.google.com/document/d/1gZFPP8yXjPazaJDP9EmFORi88R-jSytH6TTgMxTGQSk/
"""
from __future__ import absolute_import
from __future__ import unicode_literals
import copy
from collections import Counter, defaultdict, namedtuple
from attr import attrs, attrib, astuple

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.functional import cached_property
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


@attrs(frozen=True)
class LocationTypeData(object):
    """read-only representation of location type attributes specified in an upload"""
    name = attrib(type=six.text_type)
    code = attrib(type=six.text_type)
    parent_code = attrib(converter=lambda code: code or ROOT_LOCATION_TYPE)
    do_delete = attrib(type=bool)
    shares_cases = attrib(type=bool)
    view_descendants = attrib(type=bool)
    index = attrib(type=int)


class LocationTypeStub(object):
    meta_data_attrs = ['name', 'code', 'shares_cases', 'view_descendants']

    def __init__(self, new_data, old_collection):
        self.new_data = new_data
        self.code = new_data.code
        self.parent_code = new_data.parent_code
        self.do_delete = new_data.do_delete
        self.old_collection = old_collection
        self.domain = old_collection.domain_name
        self.old_version = self.old_collection.types_by_code.get(self.code)
        self.is_new = self.old_version is None

    @property
    @memoized
    def db_object(self):
        if self.is_new:
            obj = LocationType(domain=self.domain)
        else:
            obj = copy.copy(self.old_version)
        for attr in self.meta_data_attrs:
            setattr(obj, attr, getattr(self.new_data, attr, None))
        return obj

    @property
    @memoized
    def needs_save(self):
        if self.is_new or self.do_delete:
            return True

        # check if any attributes are being updated
        for attr in self.meta_data_attrs:
            if getattr(self.old_version, attr, None) != getattr(self.new_data, attr, None):
                return True

        # check if the parent is being updated
        old_parent_code = self.old_version.parent_type.code \
            if self.old_version.parent_type else ROOT_LOCATION_TYPE
        if old_parent_code != self.parent_code:
            return True

        return False


def lowercase_string(val):
    return six.text_type(val).lower()


def string_or_none(val):
    return six.text_type(val) if val else None


@attrs(frozen=True)
class LocationData(object):
    """read-only representation of location attributes specified in an upload"""
    name = attrib(type=six.text_type)
    site_code = attrib(converter=lowercase_string)
    location_type = attrib(type=six.text_type)
    parent_code = attrib(converter=lambda val: lowercase_string(val) if val else ROOT_LOCATION_TYPE)
    location_id = attrib(type=six.text_type)
    do_delete = attrib(type=bool)
    external_id = attrib(type=six.text_type)
    latitude = attrib(converter=string_or_none)
    longitude = attrib(converter=string_or_none)
    # This can be a dict or 'NOT_PROVIDED_IN_EXCEL'
    custom_data = attrib()
    delete_uncategorized_data = attrib(type=bool)
    index = attrib(type=int)


class LocationStub(object):
    titles = LOCATION_SHEET_HEADERS
    NOT_PROVIDED = 'NOT_PROVIDED_IN_EXCEL'
    meta_data_attrs = ['name', 'site_code', 'latitude', 'longitude', 'external_id']

    def __init__(self, new_data, location_data_model, old_collection):
        self.new_data = new_data
        self.site_code = new_data.site_code
        self.parent_code = new_data.parent_code
        self.index = new_data.index
        self.location_type = new_data.location_type
        self.do_delete = new_data.do_delete
        self.location_id = new_data.location_id
        self.data_model = location_data_model
        self.old_collection = old_collection
        self.domain = old_collection.domain_name

        # If a location ID is not provided, the location is presumed to be new
        self.is_new = not self.new_data.location_id

    @cached_property
    def old_version(self):
        if self.is_new:
            return None
        return self.old_collection.locations_by_id[self.location_id]

    @cached_property
    def db_object(self):
        # The SQLLocation object, either an unsaved or the actual database
        # object depending on whether 'is_new' is True or not
        if self.is_new:
            db_object = SQLLocation(domain=self.domain)
        else:
            db_object = copy.copy(self.old_version)
        for attr in self.meta_data_attrs:
            setattr(db_object, attr, getattr(self.new_data, attr, None))
        db_object.metadata = self.custom_data
        return db_object

    @cached_property
    def custom_data(self):
        # This just compiles the custom location data, the validation is done in _custom_data_errors()
        data_provided = self.new_data.custom_data != self.NOT_PROVIDED
        if data_provided:
            metadata = {key: six.text_type(value) for key, value in self.new_data.custom_data.items()}
        elif self.is_new:
            metadata = {}
        else:
            metadata = copy.copy(self.old_version.metadata)

        metadata, unknown = self.data_model.get_model_and_uncategorized(metadata)
        if data_provided and not self.new_data.delete_uncategorized_data:
            # add back uncategorized data to new metadata
            metadata.update(unknown)

        return metadata

    def get_new_parent_stub(self, location_stubs_by_code):
        parent_code = self.new_data.parent_code
        if parent_code and parent_code != ROOT_LOCATION_TYPE:
            return location_stubs_by_code[parent_code]

    @cached_property
    def needs_save(self):
        if self.is_new or self.do_delete:
            return True

        for attr in self.meta_data_attrs:
            old_value = getattr(self.old_version, attr, None)
            new_value = getattr(self.new_data, attr, None)
            if (old_value or new_value) and old_value != new_value:
                # attributes are being updated
                return True

        if self.db_object.metadata != self.old_version.metadata:
            # custom location data is being updated
            return True

        if self.location_type != self.old_version.location_type.code:
            # foreign-key refs are being updated
            return True

        if self.old_version.parent_id is not None:
            old_parent_code = self.old_collection.locations_by_pk[self.old_version.parent_id].site_code
        else:
            old_parent_code = ROOT_LOCATION_TYPE
        return old_parent_code != self.new_data.parent_code


class UnexpectedState(Exception):
    pass


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
    def locations_by_pk(self):
        return {l.id: l for l in self.locations}

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
        locs_by_pk = self.locations_by_pk
        locs_by_parent = defaultdict(list)
        for loc in self.locations:
            if loc.parent_id is not None:
                parent_code = locs_by_pk[loc.parent_id].site_code
            else:
                parent_code = ''
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

    def validate_and_parse_data_from_excel(self):
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

        type_data = [self._get_type_data(index, row)
                      for index, row in enumerate(type_sheet_reader)]

        # all locations sheets should have correct headers
        location_data = []
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
                location_data.extend([
                    self._get_location_data(index, row, sheet_name)
                    for index, row in enumerate(sheet_reader)
                ])
        return type_data, location_data

    @staticmethod
    def _get_type_data(index, row):
        titles = LOCATION_TYPE_SHEET_HEADERS
        name = row.get(titles['name'])
        code = row.get(titles['code'])
        parent_code = row.get(titles['parent_code'])
        do_delete = row.get(titles['do_delete'], 'N').lower() in ['y', 'yes']
        shares_cases = row.get(titles['shares_cases'], 'N').lower() in ['y', 'yes']
        view_descendants = row.get(titles['view_descendants'], 'N').lower() in ['y', 'yes']
        return LocationTypeData(name, code, parent_code, do_delete, shares_cases,
                                view_descendants, index)

    @staticmethod
    def _get_location_data(index, row, location_type):
        titles = LOCATION_SHEET_HEADERS
        name = row.get(titles['name'])
        site_code = row.get(titles['site_code'])
        location_type = location_type
        location_id = row.get(titles['location_id'])
        parent_code = row.get(titles['parent_code'])
        latitude = row.get(titles['latitude'])
        longitude = row.get(titles['longitude'])
        do_delete = row.get(titles['do_delete'], 'N').lower() in ['y', 'yes']
        external_id = row.get(titles['external_id'])

        def _optional_attr(attr):
            if titles[attr] in row:
                val = row.get(titles[attr])
                if type(val) == dict and '' in val:
                    # when excel header is 'data: ', the value is parsed as {'': ''}, but it should be {}
                    val.pop('')
                return val
            else:
                return LocationStub.NOT_PROVIDED

        custom_data = _optional_attr('custom_data')
        delete_uncategorized_data = row.get(titles['delete_uncategorized_data'], 'N').lower() in ['y', 'yes']
        stub = LocationData(name, site_code, location_type, parent_code, location_id,
                            do_delete, external_id, latitude, longitude, custom_data,
                            delete_uncategorized_data, index)
        return stub


class NewLocationImporter(object):
    """
    This takes location type and location stubs, validates data and the tree
    and saves the changes in a transaction.
    """

    def __init__(self, domain, type_data, location_data, user, excel_importer=None, chunk_size=100):
        self.domain = domain
        self.domain_obj = Domain.get_by_name(domain)
        self.old_collection = LocationCollection(self.domain_obj)
        self.type_stubs = [LocationTypeStub(data, self.old_collection) for data in type_data]
        data_model = get_location_data_model(self.domain)
        self.location_rows = [LocationStub(data, data_model, self.old_collection)
                              for data in location_data]
        self.user = user
        self.result = LocationUploadResult()
        self.excel_importer = excel_importer  # excel_importer is used for providing progress feedback
        self.chunk_size = chunk_size

    def run(self):
        tree_validator = LocationTreeValidator(self.type_stubs, self.location_rows, self.old_collection, self.user)
        self.result.errors = tree_validator.errors
        self.result.warnings = tree_validator.warnings
        if self.result.errors:
            return self.result

        self.bulk_commit(self.type_stubs, self.location_rows)

        return self.result

    def bulk_commit(self, type_stubs, location_stubs):
        type_objects = save_types(type_stubs, self.excel_importer)
        save_locations(location_stubs, type_objects, self.old_collection,
                       self.domain, self.excel_importer, self.chunk_size)
        # Since we updated LocationType objects in bulk, some of the post-save logic
        # that occurs inside LocationType.save needs to be explicitly called here
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
    """Validates the given type and location stubs

    All types and location stubs are linked with a corresponding
    db_object, locations also get a parent object (new_parent), by
    the time validation is complete if/when there are no errors.

    :param type_stubs: List of `LocationTypeStub` objects.
    :param location_rows: List of `LocationStub` objects.
    :param old_collection: `LocationCollection`.
    """

    def __init__(self, type_stubs, location_rows, old_collection, user):

        _to_be_deleted = lambda items: [i for i in items if i.do_delete]
        _not_to_be_deleted = lambda items: [i for i in items if not i.do_delete]

        self.user = user
        self.all_listed_types = type_stubs
        self.location_types = _not_to_be_deleted(type_stubs)
        self.types_to_be_deleted = _to_be_deleted(type_stubs)

        self.all_listed_locations = location_rows
        self.locations = _not_to_be_deleted(location_rows)
        self.locations_to_be_deleted = _to_be_deleted(location_rows)

        self.old_collection = old_collection

        self.types_by_code = {lt.code: lt for lt in self.location_types}
        self.locations_by_code = {l.site_code: l for l in location_rows}

        self.errors = self._get_errors()
        self.warnings = self._get_warnings()

    def _get_warnings(self):
        return [
            _("Location deletion in sheet '{type}', row '{i}' is ignored, "
              "as the location does not exist")
            .format(type=loc.location_type, i=loc.index)
            for loc in self.all_listed_locations
            if loc.is_new and loc.do_delete
        ]

    def _get_errors(self):
        # We want to find as many errors as possible up front, but some high
        # level errors make it unrealistic to keep validating

        location_row_errors = (self._check_unknown_location_ids() + self._validate_geodata())

        # all old types/locations should be listed in excel
        unknown_or_missing_errors = self._check_unlisted_type_codes()

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
        errors = self._validate_location_tree() + self._check_required_locations_missing()

        errors.extend(self._custom_data_errors())

        # Location names must be unique among siblings
        errors.extend(self._check_location_names())

        # Model field validation must pass
        errors.extend(self._check_model_validation())

        return errors

    def _validate_geodata(self):
        errors = []
        for loc_stub in self.all_listed_locations:
            l = loc_stub.new_data
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

    def _check_required_locations_missing(self):
        if not self.locations_to_be_deleted:
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

    def _check_unique_type_codes(self):
        counts = list(Counter(lt.code for lt in self.all_listed_types).items())
        return [
            _("Location type code '{}' is used {} times - they should be unique")
            .format(code, count)
            for code, count in counts if count > 1
        ]

    def _check_unique_location_codes(self):
        counts = list(Counter(l.site_code for l in self.all_listed_locations).items())
        return [
            _("Location site_code '{}' is used {} times - they should be unique")
            .format(code, count)
            for code, count in counts if count > 1
        ]

    def _check_unique_location_ids(self):
        counts = list(Counter(l.location_id for l in self.all_listed_locations if l.location_id).items())
        return [
            _("Location location_id '{}' is listed {} times - they should be listed once")
            .format(location_id, count)
            for location_id, count in counts if count > 1
        ]

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

    def _check_unknown_location_ids(self):
        # count location_ids listed in the excel that are not found in the domain
        old = self.old_collection.locations_by_id
        listed = {l.location_id: l for l in self.all_listed_locations if l.location_id}
        unknown = set(listed.keys()) - set(old.keys())

        return [
            _("Location 'id: {id}' is not found in your domain. It's listed in the sheet {type} at row {index}")
            .format(id=l_id, type=listed[l_id].location_type, index=listed[l_id].index)
            for l_id in unknown
        ]

    def _custom_data_errors(self):
        validator = self.old_collection.custom_data_validator
        return [
            _("Problem with custom data for location '{site_code}', in sheet '{type}', at index '{i}' - '{er}'")
            .format(site_code=l.site_code, type=l.location_type, i=l.index, er=validator(l.custom_data))
            for l in self.all_listed_locations
            if l.custom_data is not LocationStub.NOT_PROVIDED and validator(l.custom_data)
        ]

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

    def _check_location_names(self):
        locs_by_parent = defaultdict(list)
        for loc in self.locations:
            locs_by_parent[loc.parent_code].append(loc)
        errors = []
        for parent, siblings in locs_by_parent.items():
            counts = list(Counter(l.new_data.name for l in siblings).items())
            for name, count in counts:
                if count > 1:
                    errors.append(
                        (_("There are {} locations with the name '{}' under the parent '{}'")
                         .format(count, name, parent))
                    )
        return errors

    def _check_model_validation(self):
        """Do model validation"""
        errors = []
        for location in self.locations:
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


def new_locations_import(domain, excel_importer, user):
    try:
        validator = LocationExcelValidator(domain, excel_importer)
        type_data, location_data = validator.validate_and_parse_data_from_excel()
    except LocationExcelSheetError as e:
        result = LocationUploadResult()
        result.errors = [str(e)]
        return result

    importer = NewLocationImporter(domain, type_data, location_data, user, excel_importer)
    return importer.run()


def save_types(type_stubs, excel_importer=None):
    """
    Given a list of LocationTypeStub objects, saves them to SQL as LocationType objects

    :param type_stubs: (list) list of LocationType objects with meta-data attributes and
          `needs_save`, 'is_new', 'db_object' set correctly
    :param excel_importer: Used for providing progress feedback. Disabled on None

    :returns: (dict) a dict of {object.code: object for all type objects}
    """

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


def save_locations(location_stubs, types_by_code, old_collection, domain,
                   excel_importer=None, chunk_size=100):
    """
    :param location_stubs: (list) List of LocationStub objects with
        attributes like 'db_object', 'needs_save', 'do_delete' set
    :param types_by_code: (dict) Mapping of 'code' to LocationType SQL objects
    :param excel_importer: Used for providing progress feedback. Disabled on None

    This recursively saves tree top to bottom.
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

    location_stubs_by_code = {stub.site_code: stub for stub in location_stubs}
    delete_locations = []
    for stubs in chunked(order_by_location_type(), chunk_size):
        with transaction.atomic():
            for loc in stubs:
                if loc.do_delete:
                    if loc.is_new:
                        if excel_importer:
                            excel_importer.add_progress()
                    else:
                        delete_locations.append(loc)
                    continue
                if excel_importer:
                    excel_importer.add_progress()
                if loc.needs_save:
                    loc_object = loc.db_object
                    loc_object.location_type = types_by_code.get(loc.location_type)
                    parent_code = loc.parent_code
                    if parent_code == ROOT_LOCATION_TYPE:
                        loc_object.parent = None
                    elif parent_code:
                        if parent_code in location_stubs_by_code:
                            loc_object.parent = location_stubs_by_code[parent_code].db_object
                        else:
                            loc_object.parent = old_collection.locations_by_site_code[parent_code]
                    loc_object.save()

    _seen = set()

    def iter_unprocessed_ancestor_ids(stubs):
        # Returns a generator of all ancestor IDs of locations in 'stubs' which
        # haven't already been returned in a previous call
        for loc in stubs:
            if not loc.is_new:
                pk = loc.db_object.pk
                while pk is not None and pk not in _seen:
                    _seen.add(pk)
                    location = old_collection.locations_by_pk[pk]
                    yield location.location_id
                    pk = location.parent_id

    # reverse -> delete leaf nodes first
    for stubs in chunked(reversed(delete_locations), chunk_size):
        to_delete = [loc.db_object for loc in stubs]
        ancestor_ids = list(iter_unprocessed_ancestor_ids(stubs))
        with transaction.atomic():
            SQLLocation.bulk_delete(to_delete, ancestor_ids)
            if excel_importer:
                excel_importer.add_progress(len(to_delete))
