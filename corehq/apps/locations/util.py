from corehq.apps.commtrack.dbaccessors import get_supply_point_ids_in_domain_by_location
from corehq.apps.products.models import Product
from corehq.apps.locations.models import Location, SQLLocation
from corehq.apps.locations.const import LOCATION_TYPE_SHEET_HEADERS, LOCATION_SHEET_HEADERS
from corehq.apps.domain.models import Domain
from corehq.form_processor.interfaces.supply import SupplyInterface
from corehq.util.quickcache import quickcache
from corehq.util.workbook_json.excel import flatten_json, json_to_headers
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.couch.loosechange import map_reduce
from couchexport.writers import Excel2007ExportWriter
from StringIO import StringIO
from corehq.apps.consumption.shortcuts import get_loaded_default_monthly_consumption, build_consumption_dict


def load_locs_json(domain, selected_loc_id=None, include_archived=False,
        user=None, only_administrative=False):
    """initialize a json location tree for drill-down controls on
    the client. tree is only partially initialized and branches
    will be filled in on the client via ajax.

    what is initialized:
    * all top level locs
    * if a 'selected' loc is provided, that loc and its complete
      ancestry

    only_administrative - if False get all locations
                          if True get only administrative locations
    """
    from .permissions import (user_can_edit_location, user_can_view_location,
        user_can_access_location_id)

    def loc_to_json(loc, project):
        ret = {
            'name': loc.name,
            'location_type': loc.location_type.name,  # todo: remove when types aren't optional
            'uuid': loc.location_id,
            'is_archived': loc.is_archived,
            'can_edit': True
        }
        if user:
            if user.has_permission(domain, 'access_all_locations'):
                ret['can_edit'] = user_can_edit_location(user, loc, project)
            else:
                ret['can_edit'] = user_can_access_location_id(domain, user, loc.location_id)
        return ret

    project = Domain.get_by_name(domain)

    locations = SQLLocation.root_locations(
        domain, include_archive_ancestors=include_archived
    )

    if only_administrative:
        locations = locations.filter(location_type__administrative=True)

    loc_json = [
        loc_to_json(loc, project) for loc in locations
        if user is None or user_can_view_location(user, loc, project)
    ]

    # if a location is selected, we need to pre-populate its location hierarchy
    # so that the data is available client-side to pre-populate the drop-downs
    if selected_loc_id:
        selected = SQLLocation.objects.get(
            domain=domain,
            location_id=selected_loc_id
        )

        lineage = selected.get_ancestors()

        parent = {'children': loc_json}
        for loc in lineage:
            children = loc.child_locations(include_archive_ancestors=include_archived)
            if only_administrative:
                children = children.filter(location_type__administrative=True)

            # find existing entry in the json tree that corresponds to this loc
            try:
                this_loc = [k for k in parent['children'] if k['uuid'] == loc.location_id][0]
            except IndexError:
                # if we couldn't find this location the view just break out of the loop.
                # there are some instances in viewing archived locations where we don't actually
                # support drilling all the way down.
                pass
            this_loc['children'] = [
                loc_to_json(loc, project) for loc in children
                if user is None or user_can_view_location(user, loc, project)
            ]
            parent = this_loc

    return loc_json


def location_hierarchy_config(domain):
    return [(loc_type.name, [loc_type.parent_type.name
                             if loc_type.parent_type else None])
            for loc_type in Domain.get_by_name(domain).location_types]


def parent_child(domain):
    """
    Returns a dict mapping from a location type to its possible
    child types
    """
    return map_reduce(lambda (k, v): [(p, k) for p in v],
                      data=dict(location_hierarchy_config(domain)).iteritems())


@quickcache(['domain'], timeout=60)
def get_location_data_model(domain):
    from .views import LocationFieldsView
    from corehq.apps.custom_data_fields import CustomDataFieldsDefinition
    return CustomDataFieldsDefinition.get_or_create(
        domain,
        LocationFieldsView.field_type,
    )


class LocationExporter(object):

    def __init__(self, domain, include_consumption=False):
        self.domain = domain
        self.domain_obj = Domain.get_by_name(domain)
        self.include_consumption_flag = include_consumption
        self.data_model = get_location_data_model(domain)
        self.administrative_types = {}

    @property
    @memoized
    def consumption_dict(self):
        return build_consumption_dict(self.domain)

    @property
    @memoized
    def include_consumption(self):
        if bool(
            self.include_consumption_flag and
            self.domain_obj.commtrack_settings.individual_consumption_defaults
        ):
            # we'll be needing these, so init 'em:
            self.products = Product.by_domain(self.domain)
            self.product_codes = [p.code for p in self.products]
            self.supply_point_map = get_supply_point_ids_in_domain_by_location(
                self.domain)
            self.administrative_types = {
                lt.name for lt in self.domain_obj.location_types
                if lt.administrative

            }
            return True
        return False

    def get_consumption(self, loc):
        if (
            not self.include_consumption or
            loc.location_type_name in self.administrative_types or
            not self.consumption_dict
        ):
            return {}
        if loc.location_id in self.supply_point_map:
            sp_id = self.supply_point_map[loc.location_id]
        else:
            # this only happens if the supply point case did
            # not already exist
            sp_id = SupplyInterface(self.domain).get_or_create_by_location(loc).location_id
        return {
            p.code: get_loaded_default_monthly_consumption(
                self.consumption_dict,
                self.domain,
                p._id,
                loc.location_type_name,
                sp_id
            ) or ''
            for p in self.products
        }

    def _loc_type_dict(self, loc_type):

        uncategorized_keys = set()
        tab_rows = []
        for loc in Location.filter_by_type(self.domain, loc_type.name):

            model_data, uncategorized_data = \
                self.data_model.get_model_and_uncategorized(loc.metadata)

            uncategorized_keys.update(uncategorized_data.keys())

            loc_dict = {
                'location_id': loc.location_id,
                'site_code': loc.site_code,
                'name': loc.name,
                'parent_site_code': loc.parent.site_code if loc.parent else '',
                'latitude': loc.latitude or '',
                'longitude': loc.longitude or '',
                'data': model_data,
                'uncategorized_data': uncategorized_data,
                'consumption': self.get_consumption(loc),
                LOCATION_SHEET_HEADERS['external_id']: loc.external_id,
                LOCATION_SHEET_HEADERS['do_delete']: ''
            }
            tab_rows.append(dict(flatten_json(loc_dict)))

        header_keys = ['location_id', 'site_code', 'name', 'parent_code',
                       'latitude', 'longitude', 'external_id', 'do_delete']
        tab_headers = [LOCATION_SHEET_HEADERS[h] for h in header_keys]

        def _extend_headers(prefix, headers):
            tab_headers.extend(json_to_headers(
                {prefix: {header: None for header in headers}}
            ))
        _extend_headers('data', (f.slug for f in self.data_model.fields))
        _extend_headers('uncategorized_data', uncategorized_keys)
        if self.include_consumption_flag and loc_type.name not in self.administrative_types:
            _extend_headers('consumption', self.product_codes)

        sheet_title = loc_type.code

        return (sheet_title, {
            'headers': tab_headers,
            'rows': tab_rows,
        })

    def type_sheet(self, location_types):
        headers = LOCATION_TYPE_SHEET_HEADERS

        def foreign_code(lt, attr):
            val = getattr(lt, attr, None)
            if val:
                return val.code
            else:
                return None

        def coax_boolean(value):
            if isinstance(value, bool):
                value = 'yes' if value else 'no'
            return value

        rows = []
        for lt in location_types:
            type_row = {
                headers['code']: lt.code,
                headers['name']: lt.name,
                headers['parent_code']: foreign_code(lt, 'parent_type'),
                headers['do_delete']: '',
                headers['shares_cases']: coax_boolean(lt.shares_cases),
                headers['view_descendants']: coax_boolean(lt.view_descendants),
                headers['expand_from']: foreign_code(lt, 'expand_from'),
                headers['expand_to']: foreign_code(lt, 'expand_to'),
            }
            rows.append(dict(type_row))

        return ('types', {
            'headers': [headers[header] for header in ['code', 'name', 'parent_code', 'do_delete',
                        'shares_cases', 'view_descendants', 'expand_from', 'expand_to']],
            'rows': rows
        })

    def get_export_dict(self):
        location_types = self.domain_obj.location_types
        sheets = [self.type_sheet(location_types)]
        sheets.extend([
            self._loc_type_dict(loc_type)
            for loc_type in location_types
        ])
        return sheets


def dump_locations(response, domain, include_consumption=False):
    exporter = LocationExporter(domain, include_consumption=include_consumption)
    result = write_to_file(exporter.get_export_dict())
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
    header_table = [(tab_name, [tab['headers']]) for tab_name, tab in locations]
    writer.open(header_table=header_table, file=outfile)
    for tab_name, tab in locations:
        headers = tab['headers']
        tab_rows = [[row.get(header, '') for header in headers]
                    for row in tab['rows']]
        writer.write([(tab_name, tab_rows)])
    writer.close()
    return outfile.getvalue()


def get_locations_from_ids(location_ids, domain, base_queryset=None):
    """
    Returns the SQLLocations with the given location_ids, ensuring
    that they belong to the given domain. Raises SQLLocation.DoesNotExist
    if any of the locations do not match the given domain or are not
    found.
    """
    if not base_queryset:
        base_queryset = SQLLocation.objects

    location_ids = list(set(location_ids))
    expected_count = len(location_ids)

    locations = base_queryset.filter(
        domain=domain,
        is_archived=False,
        location_id__in=location_ids,
    )
    if len(locations) != expected_count:
        raise SQLLocation.DoesNotExist('One or more of the locations was not found.')
    return locations
