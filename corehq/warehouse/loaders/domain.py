from corehq.apps.domain.models import Domain
from corehq.warehouse.const import DOMAIN_STAGING_SLUG, DOMAIN_DIM_SLUG
from corehq.warehouse.dbaccessors import get_domain_ids_by_last_modified
from corehq.warehouse.etl import HQToWarehouseETLMixin, CustomSQLETLMixin
from corehq.warehouse.loaders.base import BaseStagingLoader, BaseDimLoader
from corehq.warehouse.models import DomainStagingTable, DomainDim
from dimagi.utils.couch.database import iter_docs


class DomainStagingLoader(BaseStagingLoader, HQToWarehouseETLMixin):
    """
    Represents the staging table to dump data before loading into the DomainDim

    Grain: domain_id
    """
    slug = DOMAIN_STAGING_SLUG
    model_cls = DomainStagingTable

    @classmethod
    def dependencies(cls):
        # TODO: change this to be 'context'
        # return map_slugs_to_table_names([....])
        return []

    def validate_field_mapping(self):
        # TODO: call this somewhere in tests
        model_fields = {field.name for field in self.model_cls._meta.fields}
        mapping_fields = {field for _, field in self.field_mapping()}
        missing = mapping_fields - model_fields
        if missing:
            raise Exception('Mapping fields refer to missing model fields', missing)

    @classmethod
    def field_mapping(cls):
        return [
            ('_id', 'domain_id'),
            ('name', 'domain'),
            ('default_timezone', 'default_timezone'),
            ('hr_name', 'hr_name'),
            ('creating_user_id', 'creating_user_id'),
            ('project_type', 'project_type'),

            ('is_active', 'is_active'),
            ('case_sharing', 'case_sharing'),
            ('commtrack_enabled', 'commtrack_enabled'),
            ('is_test', 'is_test'),
            ('location_restriction_for_users', 'location_restriction_for_users'),
            ('use_sql_backend', 'use_sql_backend'),
            ('first_domain_for_user', 'first_domain_for_user'),

            ('last_modified', 'domain_last_modified'),
            ('date_created', 'domain_created_on'),
            ('doc_type', 'doc_type'),
        ]

    @classmethod
    def record_iter(cls, start_datetime, end_datetime):
        domain_ids = get_domain_ids_by_last_modified(start_datetime, end_datetime)

        return iter_docs(Domain.get_db(), domain_ids)


class DomainDimLoader(BaseDimLoader, CustomSQLETLMixin):
    """
    Dimension for Domain

    Grain: domain_id
    """
    slug = DOMAIN_DIM_SLUG
    model_cls = DomainDim

    @classmethod
    def dependencies(cls):
        return [DOMAIN_STAGING_SLUG]
