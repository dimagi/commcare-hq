import re
import tempfile
from collections import OrderedDict

from django.db.models import Q

from memoized import memoized

from couchexport.models import Format
from couchexport.writers import Excel2007ExportWriter
from dimagi.utils.couch.loosechange import map_reduce
from soil import DownloadBase
from soil.util import expose_blob_download

from corehq.apps.commtrack.dbaccessors import (
    get_supply_point_ids_in_domain_by_location,
)
from corehq.apps.consumption.shortcuts import (
    build_consumption_dict,
    get_loaded_default_monthly_consumption,
)
from corehq.apps.domain.models import Domain
from corehq.apps.locations.const import (
    LOCATION_SHEET_HEADERS_BASE,
    LOCATION_SHEET_HEADERS_OPTIONAL,
    LOCATION_TYPE_SHEET_HEADERS,
)
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.products.models import Product
from corehq.blobs import CODES, get_blob_db
from corehq.form_processor.interfaces.supply import SupplyInterface
from corehq.util.files import safe_filename_header


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
    def loc_to_json(loc):
        return {
            'name': loc.name,
            'location_type': loc.location_type.name,  # todo: remove when types aren't optional
            'uuid': loc.location_id,
            'is_archived': loc.is_archived,
            'can_edit': True
        }

    locations = SQLLocation.root_locations(
        domain, include_archive_ancestors=include_archived
    )

    if only_administrative:
        locations = locations.filter(location_type__administrative=True)

    loc_json = [loc_to_json(loc) for loc in locations]

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
                break
            this_loc['children'] = [loc_to_json(loc) for loc in children]
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
    return map_reduce(lambda k_v: [(p, k_v[0]) for p in k_v[1]],
                      data=dict(location_hierarchy_config(domain)).items())


def get_location_data_model(domain):
    from .views import LocationFieldsView
    from corehq.apps.custom_data_fields.models import SQLCustomDataFieldsDefinition
    return SQLCustomDataFieldsDefinition.get_or_create(
        domain,
        LocationFieldsView.field_type,
    )


class LocationExporter(object):

    def __init__(self, domain, include_consumption=False, root_location_id=None,
                 headers_only=False, async_task=None):
        self.domain = domain
        self.domain_obj = Domain.get_by_name(domain)
        self.include_consumption_flag = include_consumption
        self.data_model = get_location_data_model(domain)
        self.administrative_types = {}
        self.location_types = LocationType.objects.by_domain(domain)
        self.async_task = async_task
        self._location_count = None
        self._locations_exported = 0

        if headers_only:
            self.base_query = SQLLocation.objects.none()
        elif root_location_id:
            root_location = SQLLocation.objects.get(location_id=root_location_id)
            self.base_query = SQLLocation.active_objects.get_descendants(
                Q(domain=self.domain, id=root_location.id)
            )
        else:
            self.base_query = SQLLocation.active_objects.filter(
                domain=self.domain,
            )

    @property
    @memoized
    def consumption_dict(self):
        return build_consumption_dict(self.domain)

    def _increment_progress(self):
        if self._location_count is None:
            self._location_count = self.base_query.count()
            self._progress_update_chunksize = max(10, self._location_count // 100)
        self._locations_exported += 1
        if self._locations_exported % self._progress_update_chunksize == 0:
            DownloadBase.set_progress(self.async_task, self._locations_exported, self._location_count)

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
                lt.name for lt in self.location_types
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

    def get_headers(self):
        headers = OrderedDict([
            ('types', [list(LOCATION_TYPE_SHEET_HEADERS.values())])
        ])
        for loc_type in self.location_types:
            additional_headers = []
            additional_headers.extend('data: {}'.format(f.slug) for f in self.data_model.get_fields())
            if self.include_consumption_flag and loc_type.name not in self.administrative_types:
                additional_headers.extend('consumption: {}'.format(code) for code in self.product_codes)
            additional_headers.append(LOCATION_SHEET_HEADERS_OPTIONAL['uncategorized_data'])
            additional_headers.append(LOCATION_SHEET_HEADERS_OPTIONAL['delete_uncategorized_data'])

            headers[loc_type.code] = [list(LOCATION_SHEET_HEADERS_BASE.values()) + additional_headers]

        return list(headers.items())

    def write_data(self, writer):
        self._write_type_sheet(writer)
        for location_type in self.location_types:
            self._write_locations(writer, location_type)

    def _write_locations(self, writer, location_type):
        include_consumption = self.include_consumption_flag and location_type.name not in self.administrative_types

        def _row_generator(include_consumption=include_consumption):
            query = self.base_query.filter(location_type=location_type)
            for loc in query:
                model_data, uncategorized_data = self.data_model.get_model_and_uncategorized(loc.metadata)
                row_data = {
                    'location_id': loc.location_id,
                    'site_code': loc.site_code,
                    'name': loc.name,
                    'parent_code': loc.parent.site_code if loc.parent else '',
                    'external_id': loc.external_id,
                    'latitude': loc.latitude or '',
                    'longitude': loc.longitude or '',
                    'do_delete': '',
                }
                row = [row_data[attr] for attr in LOCATION_SHEET_HEADERS_BASE.keys()]
                for field in self.data_model.get_fields():
                    row.append(model_data.get(field.slug, ''))

                if include_consumption:
                    consumption_data = self.get_consumption(loc)
                    row.extend([consumption_data[code] for code in self.product_codes])

                row.append(', '.join('{}: {}'.format(*d) for d in uncategorized_data.items()))

                yield row
                self._increment_progress()

        writer.write([(location_type.code, _row_generator())])

    def _write_type_sheet(self, writer):
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
        for lt in self.location_types:
            rows.append([
                lt.code,
                lt.name,
                foreign_code(lt, 'parent_type'),
                '',  # do_delete
                coax_boolean(lt.shares_cases),
                coax_boolean(lt.view_descendants),
            ])

        writer.write([('types', rows)])


def dump_locations(domain, download_id, include_consumption, headers_only, root_location_id=None, task=None):
    exporter = LocationExporter(domain, include_consumption=include_consumption, root_location_id=root_location_id,
                                headers_only=headers_only, async_task=task)

    fd, path = tempfile.mkstemp()
    writer = Excel2007ExportWriter()
    writer.open(header_table=exporter.get_headers(), file=path)
    with writer:
        exporter.write_data(writer)

    with open(path, 'rb') as file_:
        db = get_blob_db()
        expiry_mins = 60
        db.put(
            file_,
            domain=domain,
            parent_id=domain,
            type_code=CODES.tempfile,
            key=download_id,
            timeout=expiry_mins,
        )

        file_format = Format.from_format(Excel2007ExportWriter.format)
        filename = '{}_locations'.format(domain)
        if root_location_id:
            root_location = SQLLocation.objects.get(location_id=root_location_id)
            filename += '_{}'.format(root_location.name)
        expose_blob_download(
            download_id,
            expiry=expiry_mins * 60,
            mimetype=file_format.mimetype,
            content_disposition=safe_filename_header(filename, file_format.extension),
            download_id=download_id,
        )


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


def valid_location_site_code(site_code):
    slug_regex = re.compile(r'^[-_\w\d]+$')
    return slug_regex.match(site_code)
