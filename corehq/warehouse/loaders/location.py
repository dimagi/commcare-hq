from django.db.models import Q

from corehq.apps.locations.models import SQLLocation
from corehq.warehouse.const import LOCATION_DIM_SLUG, LOCATION_STAGING_SLUG
from corehq.warehouse.etl import CustomSQLETLMixin, HQToWarehouseETLMixin
from corehq.warehouse.loaders.base import BaseLoader, BaseStagingLoader
from corehq.warehouse.models import LocationDim, LocationStagingTable


class LocationStagingLoader(HQToWarehouseETLMixin, BaseStagingLoader):
    """
    Represents the staging table to dump data before loading into the LocationDim

    Grain: location_id
    """
    slug = LOCATION_STAGING_SLUG
    model_cls = LocationStagingTable

    def field_mapping(self):
        return [
            ('domain', 'domain'),
            ('name', 'name'),
            ('site_code', 'site_code'),
            ('location_id', 'location_id'),
            ('location_type_id', 'location_type_id'),
            ('external_id', 'external_id'),
            ('supply_point_id', 'supply_point_id'),
            ('user_id', 'user_id'),
            ('id', 'sql_location_id'),
            ('parent_id', 'sql_parent_location_id'),
            ('last_modified', 'location_last_modified'),
            ('created_at', 'location_created_on'),
            ('is_archived', 'is_archived'),
            ('latitude', 'latitude'),
            ('longitude', 'longitude'),
            ('location_type.name', 'location_type_name'),
            ('location_type.code', 'location_type_code'),
            ('location_type.last_modified', 'location_type_last_modified'),
        ]

    def record_iter(self, start_datetime, end_datetime):
        return SQLLocation.objects.filter(
            Q(last_modified__gt=start_datetime, last_modified__lte=end_datetime) |
            Q(location_type__last_modified__gt=start_datetime, location_type__last_modified__lte=end_datetime)
        ).select_related('location_type').iterator()


class LocationDimLoader(CustomSQLETLMixin, BaseLoader):
    """
    Dimension for Locations

    Grain: location_id
    """
    slug = LOCATION_DIM_SLUG
    model_cls = LocationDim

    def dependant_slugs(self):
        return [LOCATION_STAGING_SLUG]
