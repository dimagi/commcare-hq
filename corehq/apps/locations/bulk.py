from decimal import Decimal, InvalidOperation

from django.utils.translation import ugettext as _
from corehq.apps.commtrack.dbaccessors import get_supply_point_case_by_location
from dimagi.utils.decorators.memoized import memoized

from corehq.apps.consumption.shortcuts import get_default_consumption, set_default_consumption_for_supply_point
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.products.models import Product
from corehq.apps.custom_data_fields.edit_entity import add_prefix

from .exceptions import LocationImportError
from .models import Location, LocationType
from .forms import LocationForm
from .util import parent_child


class LocationCache(object):
    """
    Used to cache locations in memory during a bulk upload for optimization
    """

    def __init__(self, domain):
        self.domain = domain
        # {(type,parent): {name: location}}
        self._existing_by_type = {}
        # {id: location}
        self._existing_by_id = {}

    def get(self, id):
        if id not in self._existing_by_id:
            self._existing_by_id[id] = Location.get(id)
        return self._existing_by_id[id]

    def get_by_name(self, loc_name, loc_type, parent):
        key = (loc_type, parent._id if parent else None)
        if key not in self._existing_by_type:
            existing = list(Location.filter_by_type(self.domain, loc_type, parent))
            self._existing_by_type[key] = dict((l.name, l) for l in existing)
            self._existing_by_id.update(dict((l._id, l) for l in existing))
        return self._existing_by_type[key].get(loc_name, None)

    def add(self, location):
        for id in location.path + [None]:
            # this just mimics the behavior in the couch view
            key = (location.location_type, id)
            if key in self._existing_by_type:
                self._existing_by_type[key][location.name] = location


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
                    loc['site_code'] = loc['site_code'].lower()

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
        if provided_code:
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

            sp = get_supply_point_case_by_location(loc) if consumption else None

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
                                sp._id,
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
                'id': loc._id,
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
