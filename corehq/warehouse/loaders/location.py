from django.db.models import Q

from corehq.apps.locations.models import SQLLocation
from corehq.warehouse.const import LOCATION_STAGING_SLUG, LOCATION_DIM_SLUG
from corehq.warehouse.etl import HQToWarehouseETLMixin, CustomSQLETLMixin
from corehq.warehouse.loaders.base import BaseStagingLoader, BaseLoader
from corehq.warehouse.models import LocationStagingTable, LocationDim


class LocationStagingLoader(BaseStagingLoader, HQToWarehouseETLMixin):
    """
    Represents the staging table to dump data before loading into the LocationDim

    Grain: location_id
    """
    slug = LOCATION_STAGING_SLUG
    model_cls = LocationStagingTable

    @classmethod
    def field_mapping(cls):
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

    @classmethod
    def dependencies(cls):
        return []

    @classmethod
    def record_iter(cls, start_datetime, end_datetime):
        return SQLLocation.objects.filter(
            Q(last_modified__gt=start_datetime, last_modified__lte=end_datetime) |
            Q(location_type__last_modified__gt=start_datetime, location_type__last_modified__lte=end_datetime)
        ).select_related('location_type').iterator()


class LocationDimLoader(BaseLoader, CustomSQLETLMixin):
    """
    Dimension for Locations

    Grain: location_id
    """
    slug = LOCATION_DIM_SLUG
    model_cls = LocationDim

    @classmethod
    def dependencies(cls):
        return [LOCATION_STAGING_SLUG]
