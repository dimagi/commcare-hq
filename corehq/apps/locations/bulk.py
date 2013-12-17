import csv
from corehq.apps.locations.models import Location
from corehq.apps.locations.forms import LocationForm
from corehq.apps.locations.util import defined_location_types, parent_child
import itertools
from soil import DownloadBase
from couchdbkit.exceptions import ResourceNotFound

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


def import_locations(domain, worksheets, task=None):
    processed = 0
    total_rows = sum(ws.worksheet.get_highest_row() for ws in worksheets)

    for worksheet in worksheets:
        location_type = worksheet.worksheet.title
        if location_type not in defined_location_types(domain):
            yield "location with type %s not found, this worksheet will not be imported" % location_type

        data = list(worksheet)

        for loc in data:
            yield import_location(domain, location_type, loc)['message']
            if task:
                processed += 1
                DownloadBase.set_progress(task, processed, total_rows)


def import_location(domain, location_type, location_data):
    data = dict(location_data)

    existing_id = data.pop('id', None)

    parent_id = data.pop('parent_id', None)

    form_data = {}

    parent_id_invalid = check_parent_id(parent_id, domain, location_type)
    if parent_id_invalid:
        return parent_id_invalid

    if existing_id:
        existing = Location.get(existing_id)
        if existing.location_type != location_type:
            return {
                'id': None,
                'message': "Existing location type error, type of {0} is not {1}".format(
                    existing.name, location_type
                )
            }
        parent = existing.parent_id
    else:
        existing = None
        parent = parent_id

    form_data['parent_id'] = parent
    form_data['name'] = data.pop('name')
    form_data['location_type'] = location_type

    properties = {}
    for k, v in data.iteritems():
        properties[(location_type, k)] = v

    return submit_form(
        domain,
        parent,
        form_data,
        properties,
        existing,
        location_type
    )


def check_parent_id(parent_id, domain, location_type):
    if parent_id:
        try:
            parent_obj = Location.get(parent_id)
        except ResourceNotFound:
            return {
                'id': None,
                'message': 'Parent with id {0} does not exist'.format(
                    parent_id
                )
            }
        parent_relationships = parent_child(domain)
        if location_type not in parent_relationships[parent_obj.location_type]:
            return {
                'id': None,
                'message': 'Invalid parent type of {0} for child type {1}'.format(
                    parent_obj.location_type, location_type)
            }

def anything_to_update(existing, properties, form_data):
    for prop, val in properties.iteritems():
        if getattr(existing, prop[1], None) != val:
            return True
    for key, val in form_data.iteritems():
        if getattr(existing, key, None) != val:
            return True
    return False

def submit_form(domain, parent, form_data, properties, existing, location_type):
    # don't save if there is nothing to save
    if existing and not anything_to_update(existing, properties, form_data):
        return {
            'id': existing._id,
            'message': 'no changes for %s %s' % (location_type, existing.name)
        }

    form_data.update(properties)

    form = make_form(domain, parent, form_data, existing)
    form.strict = False  # optimization hack to turn off strict validation
    if form.is_valid():
        loc = form.save()
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
                message += '{0} {1}; {2}: {3}. '.format(
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
