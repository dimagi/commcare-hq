from corehq.apps.groups.models import Group
from corehq.warehouse.const import GROUP_STAGING_SLUG, GROUP_DIM_SLUG
from corehq.warehouse.dbaccessors import get_group_ids_by_last_modified
from corehq.warehouse.etl import HQToWarehouseETLMixin, CustomSQLETLMixin
from corehq.warehouse.loaders.base import BaseStagingLoader, BaseLoader
from corehq.warehouse.models import GroupStagingTable, GroupDim
from dimagi.utils.couch.database import iter_docs


class GroupStagingLoader(BaseStagingLoader, HQToWarehouseETLMixin):
    """
    Represents the staging table to dump data before loading into the GroupDim

    Grain: group_id
    """
    slug = GROUP_STAGING_SLUG
    model_cls = GroupStagingTable

    @classmethod
    def field_mapping(cls):
        return [
            ('_id', 'group_id'),
            ('domain', 'domain'),
            ('name', 'name'),
            ('case_sharing', 'case_sharing'),
            ('reporting', 'reporting'),
            ('last_modified', 'group_last_modified'),
            ('doc_type', 'doc_type'),
            ('users', 'user_ids'),
            ('removed_users', 'removed_user_ids'),
        ]

    @classmethod
    def dependencies(cls):
        return []

    @classmethod
    def record_iter(cls, start_datetime, end_datetime):
        group_ids = get_group_ids_by_last_modified(start_datetime, end_datetime)

        return iter_docs(Group.get_db(), group_ids)


class GroupDimLoader(BaseLoader, CustomSQLETLMixin):
    """
    Dimension for Groups

    Grain: group_id
    """
    slug = GROUP_DIM_SLUG
    model_cls = GroupDim

    @classmethod
    def dependencies(cls):
        return [GROUP_STAGING_SLUG]
