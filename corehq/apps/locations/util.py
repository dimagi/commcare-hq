from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack.dbaccessors import get_supply_point_ids_in_domain_by_location
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.products.models import Product
from corehq.apps.locations.models import Location, SQLLocation
from corehq.apps.domain.models import Domain
from corehq.util.quickcache import quickcache
from corehq.util.spreadsheets.excel import flatten_json, json_to_headers
from dimagi.utils.couch.database import iter_bulk_delete
from dimagi.utils.decorators.memoized import memoized
from couchdbkit import ResourceNotFound
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
    from .permissions import user_can_edit_location, user_can_view_location
    def loc_to_json(loc, project):
        ret = {
            'name': loc.name,
            'location_type': loc.location_type.name,  # todo: remove when types aren't optional
            'uuid': loc.location_id,
            'is_archived': loc.is_archived,
            'can_edit': True
        }
        if user:
            ret['can_edit'] = user_can_edit_location(user, loc, project)
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
            this_loc = [k for k in parent['children'] if k['uuid'] == loc.location_id][0]
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


def allowed_child_types(domain, parent):
    parent_type = parent.location_type if parent else None
    return parent_child(domain).get(parent_type, [])


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
            loc.location_type in self.administrative_types or
            not self.consumption_dict
        ):
            return {}
        if loc._id in self.supply_point_map:
            sp_id = self.supply_point_map[loc._id]
        else:
            # this only happens if the supply point case did
            # not already exist
            sp_id = SupplyPointCase.get_or_create_by_location(loc)._id
        return {
            p.code: get_loaded_default_monthly_consumption(
                self.consumption_dict,
                self.domain,
                p._id,
                loc.location_type,
                sp_id
            ) or ''
            for p in self.products
        }

    def _loc_type_dict(self, loc_type):
        uncategorized_keys = set()
        tab_rows = []
        for loc in Location.filter_by_type(self.domain, loc_type):

            model_data, uncategorized_data = \
                self.data_model.get_model_and_uncategorized(loc.metadata)

            uncategorized_keys.update(uncategorized_data.keys())

            loc_dict = {
                'site_code': loc.site_code,
                'name': loc.name,
                'parent_site_code': loc.parent.site_code if loc.parent else '',
                'latitude': loc.latitude or '',
                'longitude': loc.longitude or '',
                'data': model_data,
                'uncategorized_data': uncategorized_data,
                'consumption': self.get_consumption(loc),
            }

            tab_rows.append(dict(flatten_json(loc_dict)))

        tab_headers = ['site_code', 'name', 'parent_site_code', 'latitude', 'longitude']
        def _extend_headers(prefix, headers):
            tab_headers.extend(json_to_headers(
                {prefix: {header: None for header in headers}}
            ))
        _extend_headers('data', (f.slug for f in self.data_model.fields))
        _extend_headers('uncategorized_data', uncategorized_keys)
        if self.include_consumption_flag and loc_type not in self.administrative_types:
            _extend_headers('consumption', self.product_codes)

        return (loc_type, {
            'headers': tab_headers,
            'rows': tab_rows,
        })

    def get_export_dict(self):
        return [self._loc_type_dict(loc_type.name)
                for loc_type in self.domain_obj.location_types]


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
    header_table = [(loc_type, [tab['headers']]) for loc_type, tab in locations]
    writer.open(header_table=header_table, file=outfile)
    for loc_type, tab in locations:
        headers = tab['headers']
        tab_rows = [[row.get(header, '') for header in headers]
                    for row in tab['rows']]
        writer.write([(loc_type, tab_rows)])
    writer.close()
    return outfile.getvalue()


def get_xform_location(xform):
    """
    Returns the sql location associated with the user who submitted an xform
    """
    from corehq.apps.users.models import CouchUser
    user_id = getattr(xform.metadata, 'userID', None)
    if not user_id:
        return None

    user = CouchUser.get_by_user_id(user_id)
    if hasattr(user, 'get_sql_location'):
        return user.get_sql_location(xform.domain)
    elif hasattr(user, 'sql_location'):
        return user.sql_location
    return None


def get_locations_and_children(location_ids):
    """
    Takes a set of location ids and returns a django queryset of those
    locations and their children.
    """
    return SQLLocation.objects.get_queryset_descendants(
        SQLLocation.objects.filter(location_id__in=location_ids),
        include_self=True
    )


def get_locations_from_ids(location_ids, domain):
    """
    Returns the SQLLocations with the given location_ids, ensuring
    that they belong to the given domain. Raises SQLLocation.DoesNotExist
    if any of the locations do not match the given domain or are not
    found.
    """
    location_ids = list(set(location_ids))
    expected_count = len(location_ids)

    locations = SQLLocation.objects.filter(
        domain=domain,
        is_archived=False,
        location_id__in=location_ids,
    )
    if len(locations) != expected_count:
        raise SQLLocation.DoesNotExist('One or more of the locations was not found.')
    return locations
