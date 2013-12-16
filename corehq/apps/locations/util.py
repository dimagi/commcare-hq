from corehq.apps.commtrack.psi_hacks import is_psi_domain
from corehq.apps.locations.models import Location, root_locations, CustomProperty
from corehq.apps.domain.models import Domain
from couchdbkit import ResourceNotFound
from django.utils.translation import ugettext as _
from dimagi.utils.couch.loosechange import map_reduce
from couchexport.writers import Excel2007ExportWriter
from StringIO import StringIO

def load_locs_json(domain, selected_loc_id=None):
    """initialize a json location tree for drill-down controls on
    the client. tree is only partially initialized and branches
    will be filled in on the client via ajax.

    what is initialized:
    * all top level locs
    * if a 'selected' loc is provided, that loc and its complete
      ancestry
    """
    def loc_to_json(loc):
        return {
            'name': loc.name,
            'location_type': loc.location_type,
            'uuid': loc._id,
        }
    loc_json = [loc_to_json(loc) for loc in root_locations(domain)]

    # if a location is selected, we need to pre-populate its location hierarchy
    # so that the data is available client-side to pre-populate the drop-downs
    if selected_loc_id:
        selected = Location.get(selected_loc_id)
        lineage = list(Location.view('_all_docs', keys=selected.path, include_docs=True))

        parent = {'children': loc_json}
        for loc in lineage:
            # find existing entry in the json tree that corresponds to this loc
            this_loc = [k for k in parent['children'] if k['uuid'] == loc._id][0]
            this_loc['children'] = [loc_to_json(loc) for loc in loc.children]
            parent = this_loc

    return loc_json

def location_hierarchy_config(domain):
    return [(loc_type.name, [p or None for p in loc_type.allowed_parents]) for loc_type in Domain.get_by_name(domain).commtrack_settings.location_types]

def defined_location_types(domain):
    return [k for k, v in location_hierarchy_config(domain)]

def parent_child(domain):
    return map_reduce(lambda (k, v): [(p, k) for p in v], data=dict(location_hierarchy_config(domain)).iteritems())

def allowed_child_types(domain, parent):
    parent_type = parent.location_type if parent else None
    return parent_child(domain).get(parent_type, [])

# hard-coded for now
def location_custom_properties(domain, loc_type):
    def _village_classes(domain):
        # todo: meh.
        if is_psi_domain(domain):
            return [
                _('Town'),
                _('A'),
                _('B'),
                _('C'),
                _('D'),
                _('E'),
            ]
        else:
            return [
                _('Village'),
                _('City'),
                _('Town'),
                _('Hamlet'),
            ]
    hardcoded = {
        'outlet': [
            CustomProperty(
                name='outlet_type',
                datatype='Choice',
                label='Outlet Type',
                required=True,
                choices={'mode': 'static', 'args': [
                        'CHC',
                        'PHC',
                        'SC',
                        'MBBS',
                        'Pediatrician',
                        'AYUSH',
                        'Medical Store / Chemist',
                        'RP',
                        'Asha',
                        'AWW',
                        'NGO',
                        'CBO',
                        'SHG',
                        'Pan Store',
                        'General Store',
                        'Other',
                    ]},
            ),
            CustomProperty(
                name='outlet_type_other',
                label='Outlet Type (Other)',
            ),
            CustomProperty(
                name='address',
                label='Address',
            ),
            CustomProperty(
                name='landmark',
                label='Landmark',
            ),
            CustomProperty(
                name='contact_name',
                label='Contact Name',
            ),
            CustomProperty(
                name='contact_phone',
                label='Contact Phone',
            ),
        ],
        'village': [
            CustomProperty(
                name='village_size',
                datatype='Integer',
                label='Village Size',
            ),
            CustomProperty(
                name='village_class',
                datatype='Choice',
                label='Village Class',
                choices={'mode': 'static', 'args': _village_classes(domain)},
            ),
        ],
    }
    prop_site_code = CustomProperty(
        name='site_code',
        label='SMS Code',
        required=True,
        unique='global',
    )

    try:
        properties = hardcoded[loc_type]
    except KeyError:
        properties = []

    loc_config = dict((lt.name, lt) for lt in Domain.get_by_name(domain).commtrack_settings.location_types)
    if not loc_config[loc_type].administrative:
        properties.insert(0, prop_site_code)

    return properties


def lookup_by_property(domain, prop_name, val, scope, root=None):
    if root and not isinstance(root, basestring):
        root = root._id

    index_view = 'locations/prop_index_%s' % prop_name

    startkey = [domain, val]
    if scope == 'global':
        startkey.append(None)
    elif scope == 'descendant':
        startkey.append(root)
    elif scope == 'child':
        startkey.extend([root, 1])
    else:
        raise ValueError('invalid scope type')

    return set(row['id'] for row in Location.get_db().view(index_view, startkey=startkey, endkey=startkey + [{}]))

def property_uniqueness(domain, loc, prop_name, val, scope='global'):
    def normalize(val):
        try:
            return val.lower() # case-insensitive comparison
        except AttributeError:
            return val
    val = normalize(val)

    try:
        if scope == 'siblings':
            _scope = 'child'
            root = loc.parent
        else:
            _scope = scope
            root = None
        return lookup_by_property(domain, prop_name, val, _scope, root) - set([loc._id])
    except ResourceNotFound:
        # property is not indexed
        uniqueness_set = []
        if scope == 'global':
            uniqueness_set = [l for l in all_locations(loc.domain) if l._id != loc._id]
        elif scope == 'siblings':
            uniqueness_set = loc.siblings()

        return set(l._id for l in uniqueness_set if val == normalize(getattr(l, prop_name, None)))


def get_custom_property_names(domain, loc_type):
    return [prop.name for prop in location_custom_properties(domain, loc_type)]


def dump_locations(response, domain):
    file = StringIO()
    writer = Excel2007ExportWriter()

    location_types = defined_location_types(domain)

    common_types = ['id', 'name', 'parent_id', 'latitude', 'longitude']
    writer.open(
        header_table=[
            (loc_type, [common_types + get_custom_property_names(domain, loc_type)])
            for loc_type in location_types
        ],
        file=file,
    )

    for loc_type in location_types:
        tab_rows = []
        locations = Location.filter_by_type(domain, loc_type)
        for loc in locations:
            parent_id = loc.parent._id if loc.parent else ''
            custom_prop_values = [loc[prop.name] or '' for prop in location_custom_properties(domain, loc.location_type)]
            tab_rows.append(
                [loc._id, loc.name, parent_id, loc.latitude or '', loc.longitude or ''] + custom_prop_values
            )
        writer.write([(loc_type, tab_rows)])

    writer.close()
    response.write(file.getvalue())
