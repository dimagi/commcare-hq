"""
Bulk rearrange locations.

This includes support for changing location types, changing locations' parents,
deleting things, and so on.  See the spec doc for specifics:
https://docs.google.com/document/d/1gZFPP8yXjPazaJDP9EmFORi88R-jSytH6TTgMxTGQSk/
"""
import copy
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from attr import attrib, attrs
from memoized import memoized

from dimagi.utils.chunked import chunked
from dimagi.utils.parsing import string_to_boolean

from corehq.apps.domain.models import Domain

from .const import (
    LOCATION_SHEET_HEADERS,
    LOCATION_SHEET_HEADERS_BASE,
    LOCATION_SHEET_HEADERS_OPTIONAL,
    LOCATION_TYPE_SHEET_HEADERS,
    ROOT_LOCATION_TYPE,
)
from .models import LocationType, SQLLocation
from .tree_utils import BadParentError, CycleError, assert_no_cycles
from .util import get_location_data_model


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


def to_boolean(val):
    return False if val == '' else string_to_boolean(val)


def strip(val):
    return str(val).strip()


@attrs(frozen=True)
class LocationTypeData(object):
    """read-only representation of location type attributes specified in an upload"""
    name = attrib(type=str, converter=strip)
    code = attrib(type=str, converter=strip)
    parent_code = attrib(type=str, converter=lambda code: code or ROOT_LOCATION_TYPE)
    do_delete = attrib(type=bool, converter=to_boolean)
    shares_cases = attrib(type=bool, converter=to_boolean)
    view_descendants = attrib(type=bool, converter=to_boolean)
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
        self.old_object = self.old_collection.types_by_code.get(self.code)
        self.is_new = self.old_object is None

    @property
    @memoized
    def db_object(self):
        if self.is_new:
            obj = LocationType(domain=self.domain)
        else:
            obj = copy.copy(self.old_object)
        for attr in self.meta_data_attrs:
            setattr(obj, attr, getattr(self.new_data, attr))
        return obj

    @property
    @memoized
    def needs_save(self):
        if self.is_new or self.do_delete:
            return True

        # check if any attributes are being updated
        for attr in self.meta_data_attrs:
            if getattr(self.old_object, attr) != getattr(self.new_data, attr):
                return True

        # check if the parent is being updated
        old_parent_code = self.old_object.parent_type.code \
            if self.old_object.parent_type else ROOT_LOCATION_TYPE
        if old_parent_code != self.parent_code:
            return True

        return False


def lowercase_string(val):
    return str(val).strip().lower()


def maybe_decimal(val):
    if not val:
        return None
    try:
        return Decimal(val)
    except InvalidOperation:
        return val  # invalid - this will be caught later


@attrs(frozen=True)
class LocationData(object):
    """read-only representation of location attributes specified in an upload"""
    name = attrib(type=str, converter=strip)
    site_code = attrib(type=str, converter=lowercase_string)
    location_type = attrib(type=str, converter=strip)
    parent_code = attrib(type=str,
                         converter=lambda val: lowercase_string(val) if val else ROOT_LOCATION_TYPE)
    location_id = attrib(type=str, converter=strip)
    do_delete = attrib(type=bool, converter=to_boolean)
    external_id = attrib(type=str, converter=strip)
    latitude = attrib(converter=maybe_decimal)
    longitude = attrib(converter=maybe_decimal)
    # This can be a dict or 'NOT_PROVIDED_IN_EXCEL'
    custom_data = attrib()
    delete_uncategorized_data = attrib(type=bool, converter=to_boolean)
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
    def old_object(self):
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
            db_object = copy.copy(self.old_object)
        for attr in self.meta_data_attrs:
            setattr(db_object, attr, getattr(self.new_data, attr))
        db_object.metadata = self.custom_data
        return db_object

    @cached_property
    def custom_data(self):
        # This just compiles the custom location data, the validation is done in _custom_data_errors()
        data_provided = self.new_data.custom_data != self.NOT_PROVIDED
        if data_provided:
            metadata = {key: str(value) for key, value in self.new_data.custom_data.items()}
        elif self.is_new:
            metadata = {}
        else:
            metadata = copy.copy(self.old_object.metadata)

        metadata, unknown = self.data_model.get_model_and_uncategorized(metadata)
        if data_provided and not self.new_data.delete_uncategorized_data:
            # add back uncategorized data to new metadata
            metadata.update(unknown)

        return metadata

    @cached_property
    def needs_save(self):
        if self.is_new or self.do_delete:
            return True

        for attr in self.meta_data_attrs:
            old_value = getattr(self.old_object, attr)
            new_value = getattr(self.new_data, attr)
            if (old_value or new_value) and old_value != new_value:
                # attributes are being updated
                return True

        if self._metadata_needs_save():
            return True

        if self.location_type != self.old_object.location_type.code:
            # foreign-key refs are being updated
            return True

        if self.old_object.parent_id is not None:
            old_parent_code = self.old_collection.locations_by_pk[self.old_object.parent_id].site_code
        else:
            old_parent_code = ROOT_LOCATION_TYPE
        return old_parent_code != self.new_data.parent_code

    def _metadata_needs_save(self):
        # Save only for meaningful changes - not just to add empty fields
        old_metadata, new_metadata = self.old_object.metadata, self.db_object.metadata
        return (
            # data is added or modified
            any(old_metadata.get(k, '') != new_value
                for k, new_value in new_metadata.items())
            # data is removed
            or any(k not in new_metadata for k in old_metadata.keys())
        )


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
        return {loc.id: loc for loc in self.locations}

    @property
    @memoized
    def locations_by_id(self):
        return {loc.location_id: loc for loc in self.locations}

    @property
    @memoized
    def locations_by_site_code(self):
        return {loc.site_code: loc for loc in self.locations}

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
            missing = ", ".join(expected - actual)
            extra = ", ".join(actual - expected)
            message = gettext_lazy("'types' sheet should contain headers '{expected}'. {missing}{extra}")
            raise LocationExcelSheetError(message.format(
                expected=", ".join(expected),
                missing=gettext_lazy("'{}' are missing. ").format(missing) if missing else '',
                extra=gettext_lazy("'{}' are not recognized. ").format(extra) if extra else '',
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
                    missing = ", ".join(expected - actual)
                    extra = ", ".join(actual - expected)
                    message = gettext_lazy("Locations sheet with title '{name}' should contain exactly "
                                           "'{expected}' as the sheet headers. {missing}{extra}")
                    raise LocationExcelSheetError(message.format(
                        name=sheet_name,
                        expected=", ".join(expected),
                        missing=gettext_lazy("'{}' are missing. ").format(missing) if missing else '',
                        extra=gettext_lazy("'{}' are not recognized. ").format(extra) if extra else '',
                    ))
                location_data.extend([
                    self._get_location_data(index, row, sheet_name)
                    for index, row in enumerate(sheet_reader)
                ])
        return type_data, location_data

    @staticmethod
    def _get_type_data(index, row):
        titles = LOCATION_TYPE_SHEET_HEADERS
        return LocationTypeData(
            name=row.get(titles['name']),
            code=row.get(titles['code']),
            parent_code=row.get(titles['parent_code']),
            do_delete=row.get(titles['do_delete']),
            shares_cases=row.get(titles['shares_cases']),
            view_descendants=row.get(titles['view_descendants']),
            index=index,
        )

    @staticmethod
    def _get_location_data(index, row, location_type):
        titles = LOCATION_SHEET_HEADERS

        def _optional_attr(attr):
            if titles[attr] in row:
                val = row.get(titles[attr])
                if isinstance(val, dict) and '' in val:
                    # when excel header is 'data: ', the value is parsed as {'': ''}, but it should be {}
                    val.pop('')
                return val
            else:
                return LocationStub.NOT_PROVIDED

        return LocationData(
            name=row.get(titles['name']),
            site_code=row.get(titles['site_code']),
            location_type=location_type,
            parent_code=row.get(titles['parent_code']),
            location_id=row.get(titles['location_id']),
            do_delete=row.get(titles['do_delete']),
            external_id=row.get(titles['external_id']),
            latitude=row.get(titles['latitude']),
            longitude=row.get(titles['longitude']),
            custom_data=_optional_attr('custom_data'),
            delete_uncategorized_data=row.get(titles['delete_uncategorized_data']),
            index=index,
        )


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
        self.location_stubs = [LocationStub(data, data_model, self.old_collection)
                              for data in location_data]
        self.user = user
        self.result = LocationUploadResult()
        self.excel_importer = excel_importer  # excel_importer is used for providing progress feedback
        self.chunk_size = chunk_size

    def run(self):
        tree_validator = LocationTreeValidator(self.type_stubs, self.location_stubs,
                                               self.old_collection, self.user)
        self.result.errors = tree_validator.errors
        self.result.warnings = tree_validator.warnings
        if self.result.errors:
            return self.result

        self.bulk_commit(self.type_stubs, self.location_stubs)

        return self.result

    def bulk_commit(self, type_stubs, location_stubs):
        type_objects = save_types(type_stubs, self.excel_importer)
        save_locations(location_stubs, type_objects, self.old_collection,
                       self.excel_importer, self.chunk_size)
        # Since we updated LocationType objects in bulk, some of the post-save logic
        # that occurs inside LocationType.save needs to be explicitly called here
        for lt in type_stubs:
            if (not lt.do_delete and lt.needs_save):
                obj = type_objects[lt.code]
                if not lt.is_new:
                    # supply_points would have been synced while SQLLocation.save() already
                    obj.sync_administrative_status(sync_supply_points=False)

        def update_count(locations):
            return sum(loc.needs_save and not loc.do_delete and not loc.is_new for loc in locations)

        def delete_count(locations):
            return sum(loc.do_delete for loc in locations)

        def new_count(locations):
            return sum(loc.is_new for loc in locations)

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
    db_object.

    :param type_stubs: List of `LocationTypeStub` objects.
    :param location_stubs: List of `LocationStub` objects.
    :param old_collection: `LocationCollection`.
    :param user: The user performing the upload
    """

    def __init__(self, type_stubs, location_stubs, old_collection, user):

        def to_be_deleted(stubs):
            return [stub for stub in stubs if stub.do_delete]

        def not_to_be_deleted(stubs):
            return [stub for stub in stubs if not stub.do_delete]

        self.user = user
        self.domain = old_collection.domain_name
        self.all_listed_types = type_stubs
        self.location_types = not_to_be_deleted(type_stubs)
        self.types_to_be_deleted = to_be_deleted(type_stubs)

        self.all_listed_locations = location_stubs
        self.locations = not_to_be_deleted(location_stubs)
        self.locations_to_be_deleted = to_be_deleted(location_stubs)

        self.old_collection = old_collection

        self.types_by_code = {lt.code: lt for lt in self.location_types}
        self.locations_by_code = {loc.site_code: loc for loc in location_stubs}

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

        basic_errors = (
            self._check_location_restriction()
            + self._check_unique_type_codes()
            + self._check_unique_location_codes()
            + self._check_unique_location_ids()
            + self._check_new_site_codes_available()
            + self._check_unlisted_type_codes()
            + self._check_unknown_location_ids()
            + self._validate_geodata()
        )

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

    def _check_location_restriction(self):
        if self.user.has_permission(self.domain, 'access_all_locations'):
            return []

        errors = []

        if any(lt.needs_save for lt in self.all_listed_types):
            errors.append(_('You do not have permission to add or modify location types'))

        accessible_site_codes = set(SQLLocation.active_objects
                                    .accessible_to_user(self.domain, self.user)
                                    .values_list('site_code', flat=True))
        for loc_stub in self.all_listed_locations:
            if not loc_stub.needs_save:
                # Allow users to include any loc, as long as there are no changes
                continue
            if loc_stub.is_new and loc_stub.parent_code == ROOT_LOCATION_TYPE:
                errors.append(_("You do not have permission to add top level locations"))
            elif loc_stub.is_new:
                # This checks parent_exists to allow users to create multiple
                # levels at once. Somewhere up the chain, they must have a
                # parent that exists - if it isn't accessible, they'll get an
                # error there, if not, the newly created locs are accessible by
                # extension
                parent_exists = loc_stub.parent_code in self.old_collection.locations_by_site_code
                if parent_exists and loc_stub.parent_code not in accessible_site_codes:
                    errors.append(_("You do not have permission to add locations in '{}'")
                                  .format(loc_stub.parent_code))
            else:
                if loc_stub.site_code not in accessible_site_codes:
                    errors.append(_("You do not have permission to edit '{}'")
                                  .format(loc_stub.site_code))
        return errors

    def _validate_geodata(self):
        bad_locs = []
        for loc_stub in self.all_listed_locations:
            loc = loc_stub.new_data
            if (loc.latitude and not isinstance(loc.latitude, Decimal)
                    or loc.longitude and not isinstance(loc.longitude, Decimal)):
                bad_locs.append(loc)
        return [
            _("latitude/longitude 'lat-{lat}, lng-{lng}' for location in sheet '{type}' "
              "at index {index} should be valid decimal numbers.")
            .format(type=bad_loc.location_type, index=bad_loc.index, lat=bad_loc.latitude, lng=bad_loc.longitude)
            for bad_loc in bad_locs
        ]

    def _check_required_locations_missing(self):
        if not self.locations_to_be_deleted:
            # skip this check if no old locations or no location to be deleted
            return []

        old_locs_by_parent = self.old_collection.locations_by_parent_code

        missing_locs = []
        listed_sites = {loc.site_code for loc in self.all_listed_locations}
        for location_to_be_deleted in self.locations_to_be_deleted:
            required_locs = old_locs_by_parent[location_to_be_deleted.site_code]
            missing = set([loc.site_code for loc in required_locs]) - listed_sites
            if missing:
                missing_locs.append((missing, location_to_be_deleted))

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
        counts = list(Counter(loc.site_code for loc in self.all_listed_locations).items())
        return [
            _("Location site_code '{}' is used {} times - they should be unique")
            .format(code, count)
            for code, count in counts if count > 1
        ]

    def _check_unique_location_ids(self):
        counts = list(Counter(loc.location_id for loc in self.all_listed_locations if loc.location_id).items())
        return [
            _("Location location_id '{}' is listed {} times - they should be listed once")
            .format(location_id, count)
            for location_id, count in counts if count > 1
        ]

    def _check_new_site_codes_available(self):
        updated_location_ids = {loc.location_id for loc in self.all_listed_locations
                                if loc.location_id}
        # These site codes belong to locations in the db, but not the upload
        unavailable_site_codes = {loc.site_code for loc in self.old_collection.locations
                                  if loc.location_id not in updated_location_ids}
        return [
            _("Location site_code '{code}' is in use by another location. "
              "All site_codes must be unique").format(code=loc.site_code)
            for loc in self.all_listed_locations
            if loc.site_code in unavailable_site_codes
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
        listed = {loc.location_id: loc for loc in self.all_listed_locations if loc.location_id}
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
            .format(site_code=loc.site_code, type=loc.location_type, i=loc.index, er=validator(loc.custom_data))
            for loc in self.all_listed_locations
            if loc.custom_data is not LocationStub.NOT_PROVIDED and validator(loc.custom_data)
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
            counts = list(Counter(loc.new_data.name for loc in siblings).items())
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
            exclude_fields = {"location_type"}  # Skip foreign key validation
            if not location.db_object.location_id:
                # Don't validate location_id if its blank because SQLLocation.save() will add it
                exclude_fields.add("location_id")
            try:
                location.db_object.full_clean(exclude=exclude_fields)
            except ValidationError as e:
                for field, issues in e.message_dict.items():
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


def save_locations(location_stubs, types_by_code, old_collection,
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
        for loc in location_stubs:
            location_stubs_by_type[loc.location_type].append(loc)

        top_to_bottom_locations = []

        def append_at_bottom(parent_type):
            top_to_bottom_locations.extend(location_stubs_by_type[parent_type.code])
            for child_type in types_by_parent[parent_type.code]:
                append_at_bottom(child_type)

        for top_type in types_by_parent[ROOT_LOCATION_TYPE]:
            append_at_bottom(top_type)

        return top_to_bottom_locations

    # Go through all locations and either flag for deletion or save
    location_stubs_by_code = {stub.site_code: stub for stub in location_stubs}
    to_delete = []
    for stubs in chunked(order_by_location_type(), chunk_size):
        with transaction.atomic():
            for loc in stubs:
                if loc.do_delete:
                    if loc.is_new:
                        if excel_importer:
                            excel_importer.add_progress()
                    else:
                        to_delete.append(loc)
                    continue
                if excel_importer:
                    excel_importer.add_progress()
                if loc.needs_save:
                    # attach location type and parent to location, then save
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

    _delete_locations(to_delete, old_collection, excel_importer, chunk_size)


def _delete_locations(to_delete, old_collection, excel_importer, chunk_size):
    # Delete locations in chunks.  Also assemble ancestor IDs to update, but don't repeat across chunks.
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
    for stubs in chunked(reversed(to_delete), chunk_size):
        to_delete = [loc.db_object for loc in stubs]
        ancestor_ids = list(iter_unprocessed_ancestor_ids(stubs))
        with transaction.atomic():
            SQLLocation.bulk_delete(to_delete, ancestor_ids)
            if excel_importer:
                excel_importer.add_progress(len(to_delete))
