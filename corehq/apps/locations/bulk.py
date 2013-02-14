import csv
from corehq.apps.locations.models import Location
from corehq.apps.locations.forms import LocationForm
from corehq.apps.locations.util import defined_location_types, allowed_child_types
import itertools

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
            existing = Location.filter_by_type(self.domain, loc_type, parent)
            self._existing_by_type[key] = dict((l.name, l) for l in existing)
            self._existing_by_id.update(dict((l._id, l) for l in existing))
        return self._existing_by_type[key].get(loc_name, None)

    def add(self, location):
        for id in location.lineage + [location._id, None]:
            # this just mimics the behavior in the couch view
            key = (location.location_type, id)
            if key in self._existing_by_type:
                self._existing_by_type[key][location.name] = location

def import_locations(domain, f):
    r = csv.DictReader(f)
    data = list(r)

    fields = r.fieldnames
    hierarchy_fields = []
    loc_types = defined_location_types(domain)
    for field in fields:
        if field in loc_types:
            hierarchy_fields.append(field)
        else:
            break
    property_fields = fields[len(hierarchy_fields):]

    loc_cache = LocationCache(domain)
    for loc in data:
        for m in import_location(domain, loc, hierarchy_fields, property_fields, loc_cache):
            yield m

def import_location(domain, loc_row, hierarchy_fields, property_fields, loc_cache=None):
    if loc_cache is None:
        loc_cache = LocationCache(domain)

    def get_cell(field):
        val = loc_row[field].strip()
        return val if val else None

    hierarchy = [(p, get_cell(p)) for p in hierarchy_fields]
    properties = dict((p, get_cell(p)) for p in property_fields)
    # backwards compatibility
    if 'outlet_code' in property_fields:
        properties['site_code'] = properties['outlet_code']
        del properties['outlet_code']
    terminal_type = hierarchy[-1][0]

    # create parent hierarchy if it does not exist
    parent = None
    for loc_type, loc_name in hierarchy:
        row_name = '%s %s' % (parent.name, parent.location_type) if parent else '-root-'

        # are we at the leaf loc?
        is_terminal = (loc_type == terminal_type)

        if not loc_name:
            # name is empty; this level of hierarchy is skipped
            if is_terminal and any(properties.values()):
                yield 'warning: %s properties specified on row that won\'t create a %s! (%s)' % (terminal_type, terminal_type, row_name)
            continue

        child = loc_cache.get_by_name(loc_name, loc_type, parent)
        if child:
            if is_terminal:
                yield '%s %s exists; skipping...' % (loc_type, loc_name)
        else:
            if loc_type not in allowed_child_types(domain, parent):
                yield 'error: %s %s cannot be child of %s' % (loc_type, loc_name, row_name)
                return

            data = {
                'name': loc_name,
                'location_type': loc_type,
                'parent_id': parent._id if parent else None,
            }
            if is_terminal:
                data.update(((terminal_type, k), v) for k, v in properties.iteritems())

            form = make_form(domain, parent, data)
            form.strict = False # optimization hack to turn off strict validation
            if form.is_valid():
                child = form.save()
                loc_cache.add(child)
                yield 'created %s %s' % (loc_type, loc_name)
            else:
                # TODO move this to LocationForm somehow
                forms = filter(None, [form, form.sub_forms.get(loc_type)])
                for k, v in itertools.chain(*(f.errors.iteritems() for f in forms)):
                    if k != '__all__':
                        yield 'error in %s %s; %s: %s' % (loc_type, loc_name, k, v)
                return

        parent = child


# TODO i think the parent param will not be necessary once the TODO in LocationForm.__init__ is done
def make_form(domain, parent, data):
    """simulate a POST payload from the location create/edit page"""
    location = Location(domain=domain, parent=parent)
    def make_payload(k, v):
        if hasattr(k, '__iter__'):
            prefix, propname = k
            prefix = 'props_%s' % prefix
        else:
            prefix, propname = 'main', k
        return ('%s-%s' % (prefix, propname), v)
    payload = dict(make_payload(k, v) for k, v in data.iteritems())
    return LocationForm(location, payload)

