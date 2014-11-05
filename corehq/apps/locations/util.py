from corehq.apps.commtrack.models import Product, SupplyPointCase
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.locations.models import Location, root_locations
from corehq.apps.domain.models import Domain
from couchdbkit import ResourceNotFound
from dimagi.utils.couch.loosechange import map_reduce
from couchexport.writers import Excel2007ExportWriter
from StringIO import StringIO
from corehq.apps.consumption.shortcuts import get_loaded_default_monthly_consumption, build_consumption_dict


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
    selected = Location.get_in_domain(domain, selected_loc_id)
    if selected:
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
    """
    Returns a dict mapping from a location type to its possible
    child types
    """
    return map_reduce(lambda (k, v): [(p, k) for p in v], data=dict(location_hierarchy_config(domain)).iteritems())


def allowed_child_types(domain, parent):
    parent_type = parent.location_type if parent else None
    return parent_child(domain).get(parent_type, [])


def get_loc_config(domain):
    return dict((lt.name, lt) for lt in Domain.get_by_name(domain).commtrack_settings.location_types)


def lookup_by_property(domain, prop_name, val, scope, root=None):
    if root and not isinstance(root, basestring):
        root = root._id

    if prop_name == 'site_code':
        index_view = 'locations/prop_index_site_code'
    else:
        # this was to be backwards compatible with the api
        # if this ever comes up, please take a moment to decide whether it's
        # worth changing the API to raise a less nonsensical error
        # (or change this function to not sound so general!)
        raise ResourceNotFound('missing prop_index_%s' % prop_name)

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


def get_default_column_data(domain, location_types):
    data = {
        'headers': {},
        'values': {}
    }

    if Domain.get_by_name(domain).commtrack_settings.individual_consumption_defaults:
        products = Product.by_domain(domain)

        supply_point_map = SupplyPointCase.get_location_map_by_domain(domain)

        consumption_dict = build_consumption_dict(domain)

        if not consumption_dict:
            return data

        for loc_type in location_types:
            loc = get_loc_config(domain)[loc_type]
            if not loc.administrative:
                data['headers'][loc_type] = [
                    'default_' +
                    p.code for p in products
                ]

                locations = Location.filter_by_type(domain, loc_type)
                for loc in locations:
                    if loc._id in supply_point_map:
                        sp_id = supply_point_map[loc._id]
                    else:
                        # this only happens if the supply point case did
                        # not already exist
                        sp_id = SupplyPointCase.get_or_create_by_location(loc)._id

                    data['values'][loc._id] = [
                        get_loaded_default_monthly_consumption(
                            consumption_dict,
                            domain,
                            p._id,
                            loc_type,
                            sp_id
                        ) or '' for p in products
                    ]
            else:
                data['headers'][loc_type] = []
    return data


def get_location_data_model(domain):
    from .views import LocationFieldsView
    return CustomDataFieldsDefinition.get_or_create(
        domain,
        LocationFieldsView.field_type,
    )


def dump_locations(response, domain, include_consumption=False):
    file = StringIO()
    writer = Excel2007ExportWriter()

    location_types = defined_location_types(domain)

    if include_consumption:
        defaults = get_default_column_data(domain, location_types)
    else:
        defaults = {
            'headers': {},
            'values': {}
        }

    common_types = ['site_code', 'name', 'parent_site_code', 'latitude', 'longitude']

    location_data_model = get_location_data_model(domain)
    location_data_fields = [f.slug for f in location_data_model.fields]

    writer.open(
        header_table=[
            (loc_type, [
                common_types +
                location_data_fields +
                defaults['headers'].get(loc_type, [])
            ])
            for loc_type in location_types
        ],
        file=file,
    )

    for loc_type in location_types:
        tab_rows = []
        locations = Location.filter_by_type(domain, loc_type)
        for loc in locations:
            parent_site_code = loc.parent.site_code if loc.parent else ''

            if loc._id in defaults['values']:
                default_column_values = defaults['values'][loc._id]
            else:
                default_column_values = []

            custom_data = [loc.metadata.get(slug, '')
                           for slug in location_data_fields]
            # TODO handle unschema'd location metadata?

            tab_rows.append(
                [
                    loc.site_code,
                    loc.name,
                    parent_site_code,
                    loc.latitude or '',
                    loc.longitude or '',
                ] + custom_data + default_column_values
            )
        writer.write([(loc_type, tab_rows)])

    writer.close()
    response.write(file.getvalue())
