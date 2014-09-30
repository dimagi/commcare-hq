from corehq.apps.locations.exceptions import LocationImportError
from corehq.apps.locations.models import Location
from corehq.apps.locations.forms import LocationForm
from corehq.apps.locations.util import defined_location_types, parent_child
import itertools
from soil import DownloadBase
from couchdbkit.exceptions import ResourceNotFound
from corehq.apps.consumption.shortcuts import get_default_consumption, set_default_consumption_for_supply_point
from corehq.apps.commtrack.models import Product, SupplyPointCase
from decimal import Decimal, InvalidOperation
from django.utils.translation import ugettext as _


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

        if location_type not in defined_location_types(self.domain):
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

                    self.results.append(import_location(
                        self.domain,
                        location_type,
                        loc,
                        self.parent_child_map
                    )['message'])
                self.excel_importer.add_progress()


def import_locations(domain, excel_importer):
    location_importer = LocationImporter(domain, excel_importer)
    results = location_importer.run()

    return results


def import_location(domain, location_type, location_data, parent_child_map=None):
    data = dict(location_data)

    provided_code = data.pop('site_code', None)

    parent_site_code = data.pop('parent_site_code', None)

    if not parent_child_map:
        parent_child_map = parent_child(domain)

    form_data = {}

    try:
        parent_id = _process_parent_site_code(
            parent_site_code, domain, location_type, parent_child_map
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
        existing = Location.by_site_code(domain, provided_code)
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

    properties = {}
    consumption = []
    for k, v in data.iteritems():
        if k.startswith('default_'):
            consumption.append((k[8:], v))
        else:
            properties[(location_type, k)] = v

    return submit_form(
        domain,
        parent,
        form_data,
        properties,
        existing,
        location_type,
        consumption
    )


def invalid_location_type(location_type, parent_obj, parent_relationships):
    return (
        parent_obj.location_type not in parent_relationships or
        location_type not in parent_relationships[parent_obj.location_type]
    )


def _process_parent_site_code(parent_site_code, domain, location_type, parent_child_map):
    if not parent_site_code:
        return None

    parent_obj = Location.by_site_code(domain, parent_site_code.lower())
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
        raise LocationImportError(_('Parent with site code {0} does not exist in this project').format(parent_site_code))


def no_changes_needed(domain, existing, properties, form_data, consumption, sp=None):
    if not existing:
        return False
    for prop, val in properties.iteritems():
        if getattr(existing, prop[1], None) != val:
            return False
    for key, val in form_data.iteritems():
        if getattr(existing, key, None) != val:
            return False
    for product_code, val in consumption:
        product = Product.get_by_code(domain, product_code)
        if get_default_consumption(
            domain,
            product._id,
            existing.location_type,
            existing._id
        ) != val:
            return False

    return True


def submit_form(domain, parent, form_data, properties, existing, location_type, consumption):
    # don't save if there is nothing to save
    if no_changes_needed(domain, existing, properties, form_data, consumption):
        return {
            'id': existing._id,
            'message': 'no changes for %s %s' % (location_type, existing.name)
        }

    form_data.update(properties)

    form = make_form(domain, parent, form_data, existing)
    form.strict = False  # optimization hack to turn off strict validation
    if form.is_valid():
        loc = form.save()

        sp = SupplyPointCase.get_by_location(loc) if consumption else None

        if consumption and sp:
            for product_code, value in consumption:
                product = Product.get_by_code(domain, product_code)

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
                            domain,
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
        # TODO move this to LocationForm somehow
        forms = filter(None, [form, form.sub_forms.get(location_type)])
        for k, v in itertools.chain(*(f.errors.iteritems() for f in forms)):
            if k != '__all__':
                message += u'{0} {1}; {2}: {3}. '.format(
                    location_type, form_data.get('name', 'unknown'), k, v[0]
                )

        return {
            'id': None,
            'message': message
        }

# TODO i think the parent param will not be necessary once the TODO in LocationForm.__init__ is done
def make_form(domain, parent, data, existing=None):
    """simulate a POST payload from the location create/edit page"""
    location = existing or Location(domain=domain, parent=parent)

    def make_payload(k, v):
        if hasattr(k, '__iter__'):
            prefix, propname = k
            prefix = 'props_%s' % prefix
        else:
            prefix, propname = 'main', k
        return ('%s-%s' % (prefix, propname), v)
    payload = dict(make_payload(k, v) for k, v in data.iteritems())
    return LocationForm(location, payload)
