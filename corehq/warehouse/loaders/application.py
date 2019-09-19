from dimagi.utils.couch.database import iter_docs

from corehq.apps.app_manager.models import Application
from corehq.warehouse.const import (
    APPLICATION_DIM_SLUG,
    APPLICATION_STAGING_SLUG,
)
from corehq.warehouse.dbaccessors import get_application_ids_by_last_modified
from corehq.warehouse.etl import CustomSQLETLMixin, HQToWarehouseETLMixin
from corehq.warehouse.loaders.base import BaseLoader, BaseStagingLoader
from corehq.warehouse.models import ApplicationDim, ApplicationStagingTable


class ApplicationStagingLoader(HQToWarehouseETLMixin, BaseStagingLoader):
    """
    Represents the staging table to dump data before loading into the ApplicationDim

    Grain: application_id
    """
    slug = APPLICATION_STAGING_SLUG
    model_cls = ApplicationStagingTable

    def field_mapping(self):
        return [
            ('_id', 'application_id'),
            ('domain', 'domain'),
            ('name', 'name'),
            ('last_modified', 'application_last_modified'),
            ('doc_type', 'doc_type'),
            ('version', 'version'),
            ('copy_of', 'copy_of'),
        ]

    def record_iter(self, start_datetime, end_datetime):
        application_ids = get_application_ids_by_last_modified(start_datetime, end_datetime)

        return iter_docs(Application.get_db(), application_ids)


class ApplicationDimLoader(CustomSQLETLMixin, BaseLoader):
    """
    Dimension for Applications

    Grain: application_id
    """
    slug = APPLICATION_DIM_SLUG
    model_cls = ApplicationDim

    def dependant_slugs(self):
        return [APPLICATION_STAGING_SLUG]
