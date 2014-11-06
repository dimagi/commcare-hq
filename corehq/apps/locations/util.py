from corehq.apps.commtrack.models import Product, SupplyPointCase
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.locations.models import Location, root_locations
from corehq.apps.domain.models import Domain
from dimagi.utils.excel import flatten_json, json_to_headers
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


def _loc_type_dict(domain, loc_type, data_model):
    uncategorized_keys = set()
    tab_rows = []
    for loc in Location.filter_by_type(domain, loc_type):

        model_data, uncategorized_data = \
            data_model.get_model_and_uncategorized(loc.metadata)

        uncategorized_keys.add(uncategorized_data.keys())

        loc_dict = {
            'site_code': loc.site_code,
            'name': loc.name,
            'parent_site_code': loc.parent.site_code if loc.parent else '',
            'latitude': loc.latitude or '',
            'longitude': loc.longitude or '',
            'data': model_data,
            'uncategorized_data': uncategorized_data,
        }

        # TODO format defaults to be a proper k/v mapping
        # Does it need a prefix?  How do we avoid name conflicts?
        # if loc._id in defaults['values']:
            # loc_row.update(defaults['values'][loc._id])

        tab_rows.append(dict(flatten_json(loc_dict)))

    tab_headers = ['site_code', 'name', 'parent_site_code', 'latitude', 'longitude']
    tab_headers.extend(json_to_headers(
        {'data': {field.slug: None for field in data_model.fields}}
    ))
    # TODO
    # tab_headers.extent(defaults['headers'].get(loc_type, []))
    tab_headers.extend(json_to_headers(
        {'uncategorized_data': {key: None for key in uncategorized_keys}}
    ))

    return (loc_type, {
        'headers': tab_headers,
        'rows': tab_rows,
    })


def dump_locations(response, domain, include_consumption=False):
    location_types = defined_location_types(domain)
    data_model = get_location_data_model(domain)

    # if include_consumption:
        # defaults = get_default_column_data(domain, location_types)
    # else:
        # defaults = {
            # 'headers': {},
            # 'values': {}
        # }

    locations = [_loc_type_dict(domain, loc_type, data_model)
                 for loc_type in location_types]

    result = write_to_file(locations)
    response.write(result)


def write_to_file(locations):
    """
    locations = [
        ('loc_type1', {
             'headers': ['header1', 'header2', ...]
             'rows': [
                 {
                     'header1': val1
                     'header2': val2
                 },
                 {...},
             ]
        })
    ]
    """
    outfile = StringIO()
    writer = Excel2007ExportWriter()
    writer.open(
        header_table=[
            (loc_type, tab['headers'])
            for loc_type, tab in locations
        ],
        file=outfile,
    )
    for loc_type, tab in locations:
        headers = tab['headers']
        writer.write([(
            loc_type,
            [
                [row.get(header, '') for header in headers]
                for row in tab['rows']
            ]
        )])
    writer.close()
    return outfile.getvalue()
