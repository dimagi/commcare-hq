import csv
from corehq.apps.locations.models import Location
from corehq.apps.locations.forms import LocationForm
from corehq.apps.locations.util import defined_location_types, allowed_child_types
import itertools
from soil import DownloadBase

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


def import_locations(domain, worksheet, update_existing=False, task=None):
    fields = worksheet.headers

    data = list(worksheet)

    hierarchy_fields = []
    loc_types = defined_location_types(domain)
    for field in fields:
        if field in loc_types:
            hierarchy_fields.append(field)
        else:
            break
    property_fields = fields[len(hierarchy_fields):]

    if not hierarchy_fields:
        yield 'missing location hierarchy-related fields in left columns. aborting import'
        return

    loc_cache = LocationCache(domain)
    for index, loc in enumerate(data):
        if task:
            DownloadBase.set_progress(task, index, len(data))

        for m in import_location(domain, loc, hierarchy_fields, property_fields, update_existing, loc_cache):
            yield m

def import_location(domain, loc_row, hierarchy_fields, property_fields, update, loc_cache=None):
    if loc_cache is None:
        loc_cache = LocationCache(domain)

    def get_cell(field):
        if loc_row[field]:
            return loc_row[field].strip()
        else:
            return None

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

        def save(existing=None):
            messages = []
            error = False

            data = {
                'name': loc_name,
                'location_type': loc_type,
                'parent_id': parent._id if parent else None,
            }
            if is_terminal:
                data.update(((terminal_type, k), v) for k, v in properties.iteritems())

            form = make_form(domain, parent, data, existing)
            form.strict = False # optimization hack to turn off strict validation
            if form.is_valid():
                child = form.save()
                if existing:
                    messages.append('updated %s %s' % (loc_type, loc_name))
                else:
                    loc_cache.add(child)
                    messages.append('created %s %s' % (loc_type, loc_name))
            else:
                # TODO move this to LocationForm somehow
                error = True
                child = None
                forms = filter(None, [form, form.sub_forms.get(loc_type)])
                for k, v in itertools.chain(*(f.errors.iteritems() for f in forms)):
                    if k != '__all__':
                        messages.append('error in %s %s; %s: %s' % (loc_type, loc_name, k, v))

            return child, messages, error

        child = loc_cache.get_by_name(loc_name, loc_type, parent)
        if child:
            if is_terminal:
                if update:
                    # (x or None) is to not distinguish between '' and None
                    properties_changed = any((v or None) != (getattr(child, k, None) or None) for k, v in properties.iteritems())
                    if properties_changed:
                        _, messages, _ = save(child)
                        for m in messages:
                            yield m

                    else:
                        yield '%s %s unchanged; skipping...' % (loc_type, loc_name)
                else:
                    yield '%s %s exists; skipping...' % (loc_type, loc_name)
        else:
            if loc_type not in allowed_child_types(domain, parent):
                yield 'error: %s %s cannot be child of %s' % (loc_type, loc_name, row_name)
                return

            child, messages, error = save()
            for m in messages:
                yield m
            if error:
                return

        parent = child


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

