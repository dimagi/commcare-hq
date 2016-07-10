from decimal import Decimal, InvalidOperation

from django.utils.translation import ugettext as _
from dimagi.utils.decorators.memoized import memoized
from couchdbkit import ResourceNotFound

from corehq.apps.consumption.shortcuts import get_default_consumption, set_default_consumption_for_supply_point
from corehq.apps.products.models import Product
from corehq.apps.custom_data_fields.edit_entity import add_prefix

from .exceptions import LocationImportError
from .models import Location, LocationType
from .forms import LocationForm
from .util import parent_child


def top_level_location_types(domain):
    """
    Return all location types which do not have
    any potential parents
    """
    from corehq.apps.locations.util import location_hierarchy_config
    hierarchy = location_hierarchy_config(domain)
    return [t[0] for t in hierarchy if t[1] == [None]]


class LocationImporter(object):

    def __init__(self, domain, excel_importer):
        self.domain = domain
        self.excel_importer = excel_importer

        self.processed = 0
        self.results = []
        self.seen_site_codes = set()

        self.parent_child_map = parent_child(self.domain)

        self.total_rows = sum(
            ws.worksheet.get_highest_row() for ws in self.excel_importer.worksheets
        )
        self.types = [ws.worksheet.title for ws in self.excel_importer.worksheets]
        self.top_level_types = top_level_location_types(domain)

    def run(self):
        for loc_type in self.top_level_types:
            self.import_loc_type(loc_type)

        return self.results

    def import_loc_type(self, loc_type):
        if loc_type in self.types:
            self.import_worksheet(
                self.excel_importer.worksheets[self.types.index(loc_type)]
            )

            if loc_type in self.parent_child_map:
                for child_type in self.parent_child_map[loc_type]:
                    self.import_loc_type(child_type)

    def import_worksheet(self, worksheet):
        location_type = worksheet.worksheet.title

        if not LocationType.objects.filter(
            domain=self.domain,
            name=location_type,
        ).exists():
            self.results.append(_(
                "Location with type {location_type} not found, this worksheet \
                will not be imported"
                ).format(
                    location_type=location_type
                )
            )
        else:
            for loc in worksheet:
                if 'site_code' in loc:
                    # overwrite this value in the dict so we don't
                    # ever accidentally use a randomly capitalized veersion
                    loc['site_code'] = unicode(loc['site_code']).lower()

                if 'site_code' in loc and loc['site_code'] in self.seen_site_codes:
                    self.results.append(_(
                        "Location {name} with site code {site_code} could not \
                        be imported due to duplicated site codes in the excel \
                        file"
                    ).format(
                        name=loc['name'],
                        site_code=loc['site_code']
                    ))
                else:
                    if 'site_code' in loc:
                        self.seen_site_codes.add(loc['site_code'])

                    self.results.append(self.import_location(
                        location_type,
                        loc,
                        self.parent_child_map
                    )['message'])
                self.excel_importer.add_progress()

    def import_location(self, location_type, location_data, parent_child_map=None):
        data = dict(location_data)

        provided_code = data.pop('site_code', None)
        parent_site_code = data.pop('parent_site_code', None)
        location_id = data.pop('location_id', None)

        if not parent_child_map:
            parent_child_map = parent_child(self.domain)

        form_data = {}

        try:
            parent_id = self._process_parent_site_code(
                parent_site_code, location_type, parent_child_map
            )
        except LocationImportError as e:
            return {
                'id': None,
                'message': _('Unable to import location {0}: {1}').format(
                    data.pop('name'), e
                )
            }

        existing = None
        parent = parent_id
        if location_id:
            try:
                existing = Location.get(location_id)
            except ResourceNotFound:
                return {
                    'id': None,
                    'message': _('Unable to find location for location_id {}').format(location_id),
                }
            else:
                if existing.domain != self.domain:
                    return {
                        'id': None,
                        'message': _('Invalid location_id {}').format(location_id),
                    }
        elif provided_code:
            existing = Location.by_site_code(self.domain, provided_code)

        if existing:
            if existing.location_type != location_type:
                return {
                    'id': None,
                    'message': _("Existing location type error, type of {0} is not {1}").format(
                        existing.name, location_type
                    )
                }

            parent = parent_id or existing.parent_id

        form_data['site_code'] = provided_code

        form_data['parent_id'] = parent
        form_data['name'] = data.pop('name')
        form_data['location_type'] = location_type

        lat, lon = data.pop('latitude', None), data.pop('longitude', None)
        if lat and lon:
            form_data['coordinates'] = '%s, %s' % (lat, lon)

        consumption = data.get('consumption', {}).items()

        metadata = data.get('data', {})
        metadata.update(data.get('uncategorized_data', {}))
        form_data.update(add_prefix(metadata))

        return self.submit_form(
            parent,
            form_data,
            existing,
            location_type,
            consumption,
        )

    def _process_parent_site_code(self, parent_site_code, location_type, parent_child_map):
        if not parent_site_code:
            return None

        parent_obj = Location.by_site_code(self.domain, parent_site_code.lower())
        if parent_obj:
            if invalid_location_type(location_type, parent_obj, parent_child_map):
                raise LocationImportError(
                    _('Invalid parent type of {0} for child type {1}').format(
                        parent_obj.location_type,
                        location_type
                    )
                )
            else:
                return parent_obj._id
        else:
            raise LocationImportError(
                _('Parent with site code {0} does not exist in this project')
                .format(parent_site_code)
            )

    @memoized
    def get_product(self, code):
        return Product.get_by_code(self.domain, code)

    def no_changes_needed(self, existing, form_data, consumption):
        if not existing:
            return False
        for key, val in form_data.iteritems():
            if getattr(existing, key, None) != val:
                return False

        for product_code, val in consumption:
            product = self.get_product(product_code)
            if get_default_consumption(
                self.domain,
                product._id,
                existing.location_type,
                existing._id
            ) != val:
                return False

        return True

    def submit_form(self, parent, form_data, existing, location_type, consumption):
        location = existing or Location(domain=self.domain, parent=parent)
        form = LocationForm(location, form_data, is_new=not bool(existing))
        form.strict = False  # optimization hack to turn off strict validation
        if form.is_valid():
            # don't save if there is nothing to save
            if self.no_changes_needed(existing, form_data, consumption):
                return {
                    'id': existing._id,
                    'message': 'no changes for %s %s' % (location_type, existing.name)
                }

            loc = form.save()

            sp = loc.linked_supply_point() if consumption else None

            if consumption and sp:
                for product_code, value in consumption:
                    product = self.get_product(product_code)

                    if not product:
                        # skip any consumption column that doesn't match
                        # to a real product. currently there is no easy
                        # way to alert here, though.
                        continue

                    try:
                        amount = Decimal(value)

                        # only set it if there is a non-negative/non-null value
                        if amount and amount >= 0:
                            set_default_consumption_for_supply_point(
                                self.domain,
                                product._id,
                                sp.case_id,
                                amount
                            )
                    except (TypeError, InvalidOperation):
                        # should inform user, but failing hard due to non numbers
                        # being used on consumption is strange since the
                        # locations would be in a very inconsistent state
                        continue

            if existing:
                message = 'updated %s %s' % (location_type, loc.name)
            else:
                message = 'created %s %s' % (location_type, loc.name)

            return {
                'id': loc.location_id,
                'message': message
            }
        else:
            message = 'Form errors when submitting: '
            for k, v in form.errors.iteritems():
                if k != '__all__':
                    message += u'{0} {1}; {2}: {3}. '.format(
                        location_type, form_data.get('name', 'unknown'), k, v[0]
                    )

            return {
                'id': None,
                'message': message
            }


def import_locations(domain, excel_importer):
    location_importer = LocationImporter(domain, excel_importer)
    results = location_importer.run()

    return results


def invalid_location_type(location_type, parent_obj, parent_relationships):
    return (
        parent_obj.location_type not in parent_relationships or
        location_type not in parent_relationships[parent_obj.location_type]
    )


class LocationTypeRow(object):
    def __init__(row):
        self.level_name = row.get('Level Name', '')
        self.owns_cases = (row.get('Owns Cases (Y/N) ') or '').lower() == 'y'
        self.view_child_cases = (row.get('Owns Cases (Y/N) ') or '').lower() == 'y'
        self.do_delete = row.get(self.titles['do_delete'], 'N').lower() in ['y', 'yes']
        # a reason for hardfail of import, to be displayed back to user
        self.hardfail_reason = None


class LocationRow(object):
    titles = {
        'id': 'Location ID',
        'code': 'Location Code',
        'name': 'Name',
        'parent': 'Parent',
        'gps_lat': 'GPS - Lat',
        'gps_lang': 'GPS - Lang',
        'do_delete': 'Delete Y/N'
    }

    def __init__(self, row):
        self.id = row.get(self.titles['id'])
        self.code = row.get(self.titles['code'])
        self.name = row.get(self.titles['name'])
        self.parent = row.get(self.titles['parent'])
        self.gps_lat = row.get(self.titles['gps_lat'])
        self.gps_lang = row.get(self.titles['gps_lang'])
        self.do_delete = row.get(self.titles['do_delete'], 'N').lower() in ['y', 'yes']
        self.hardfail_reason = None
        self.warnings = []

    def validate_extra_data(self):
        # should validate all data except parent/child relation
        # and return (warnings, errors)
        return [], []


class LocationUploadResult(object):
    def __init__(self):
        self.success = True
        self.messages = []
        self.errors = []
        self.warnings = []


class LocationAccessorMixin(object):
    """
    A collection of existing locations to pre-upload
    """
    @memoized
    @property
    def old_locations(self):
        domain_obj = Domain.get_by_name(self.domain)
        types = self.domain_obj.location_types
        return [Location.filter_by_type(self.domain, loc_type.name) for loc_type in types ]

    @memoized
    @property
    def index_by_site_code(self):
        return {l.site_code: l for l in self.old_locations}

    @memoized
    @property
    def index_by_id(self):
        return {l._id: l for l in self.old_locations}

    def by_site_code(self, site_code):
        return self.index_by_site_code.get(site_code)

    def by_id(self, id):
        return self.index_by_id.get(id)


class LocationTypeHelper(object):
    """
    A collection of valiadted location type rows and helper methods that
    NewLocationImporter.import_locations() can use
    """
    def __init__(self, type_rows):
        self.type_rows = type_rows
        self.index_by_level = {lt.level_name: lt for lt in type_rows}
        self.parents_by_level = {lt.level_name: lt.parent_type for lt in type_rows}

    def is_valid_child_parent(self, child_level, parent_level):
        # returns True if child_level is actual child_level of parent_level
        parent_type = self.parents_by_level.get(child_level)
        return parent_type.level_name == parent_level




class NewLocationImporter(LocationAccessorMixin):

    self.types_sheet_title = "types"
    self.locations_sheet_title = "locations"

    def __init__(self, domain, excel_importer, location_rows=None):
        self.domain = domain
        self.domain_obj = Domain.get_by_name(domain)
        self.excel_importer = excel_importer
        self.sheets_by_title = self.get_sheets_by_title()
        self.location_rows = self.sheets_by_title[self.locations_sheet_title]

    def get_sheets_by_title(self):
        # validate excel format/headers
        sheets_by_title = {ws.title: ws for ws in self.excel_importer.worksheets}
        if self.types_sheet_title not in self.sheets_by_title:
            raise LocationImportError("'types' sheet is required")
        if self.locations_sheet_title not in self.sheets_by_title:
            raise LocationImportError("'locations' sheet is required")
        return sheets_by_title

    def run(self):
        result = LocationUploadResult()
        type_rows = self.import_types(result)

        if result.sucess:
            location_types_helper = LocationTypeHelper(type_rows)
            location_rows = self.import_locations(result, location_types_helper)

        if result.sucess:
            self.commit_changes(type_rows, location_rows, result)

        return result

    def import_types(self, result):
        # Validates given locations types, returns list of LocationTypeRow to be saved
        # can't point to itself
        # no cycles
        # no type should point to to-be-deleted types
        # valid expand to and from
        # if the import should hardfail, result.success should be set to False
        # and a error-message for hardfail can be set on errored LocationTypeRow.hardfail_reason
        return []

    def import_locations(self, result, location_types_helper):

        # Failures Modes?
            # if same location_id/site_code/level_name occur twice, should the first one succeed
            # and rest fail?
            # Assumption: We should hardfail on everything, because we can't determine which item
            # in the duplicated items get pointed from children

        old_locations = self.old_locations
        old_location_ids = [l.id for l in old_locations]

        seen_loc_ids = []
        seen_site_codes = []
        error_messages = []
        hardfail = False

        # index location_rows
        location_rows_by_id = {}
        location_rows_by_site_code = {}

        for count, location in enumerate(self.location_rows):
            location = LocationRow(location)
            # get loc_id and site_code
            if location._id:
                site_code = location.site_code or site_code_by_id(location._id) or None
                loc_id = location._id
            else:
                if location.site_code:
                    loc_id = location._id or loc_id_by_site_code(location.site_code) or None
                    site_code = location.site_code
                else:
                    loc_id, site_code = None, None
            # add to index
            if loc_id:
                location_rows_by_id[loc_id] = location
            if site_code
                location_rows_by_site_code[site_code] = location

            # check for duplicates
            if loc_id:
                if loc_id not in old_location_ids:
                    location.hardfail_reason = "Unknown Location ID"
                    # hardfail unknown
                    # unknown_loc_ids.append(loc_id)
                if loc_id in seen_loc_ids:
                    location.hardfail_reason = "duplicate location_id"
                    # hardfail duplicate
                    # duplicate_loc_ids.append(loc_id)
            if site_code:
                if site_code in seen_site_codes:
                    location.hardfail_reason = "duplicate site_code"
                    # hardfail
            if not site_code and no loc_id:
                # ignore and warning
                result.warning("No id or site_code for row at {}".format(count))

            # get parent_location
            if location.parent in [loc_id, site_code]:
                location.hardfail_reason = "Pointing to itself"
            if location.parent in old_location_ids:
                # parent ref must be a location_id
                parent_location_row = location_rows_by_id.get(location.parent, None)
            else:
                # parent ref must be a site_code
                parent_location_row = location_rows_by_site_code.get(location.parent, None)

            # validate eligibile parent
            if not parent_location_row:
                location.hardfail_reason = "Unknown parent"
            if parent_location.do_delete and not location.do_delete:
                location.hardfail_reason = "Pointing to a to-be-deleted location"
            elif parent_location_row.hardfail_reason:
                location.hardfail_reason = "Problem with parent: ()".format(parent_location_row.hardfail_reason)

            # parent child validation
            TOP = "TOP"
            location_level = location.level or TOP
            parent_level = parent_location_row.level
            if not location_type_helper.is_valid_child_parent(location_level, parent_level):
                location.hardfail_reason = "Invalid parent location"

            # validate extra information
            warnings, data_errors = location.validate_extra_data()
            location.warnings = warnings
            if data_errors:
                location.hardfail_reason = data_errors

            if not location.hardfail_reason:
                valid_location_rows.append(location)
            else:
                result.sucess = False
                error_messages = "Problem with row at index {count}: {problem} ".format(
                    count=count,
                    problem=location.hardfail_reason
                )

            seen_loc_ids.append(loc_id)
            seen_site_codes.append(site_code)
        # fail if errors
        missing_locations = set(old_location_ids) - set(seen_loc_ids)
        if missing_locations:
            error_messages = (
                "All exisitng locations must be listed. Locations with following IDs are missing: {}".format(
                    list(missing_locations)
                )
            )
        return valid_location_rows

        self.commit_changes(self, type_rows, location_rows, result):
            # should be called after all validation is done, this is where actual save happens
            return False
