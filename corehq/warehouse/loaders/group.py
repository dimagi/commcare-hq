from dimagi.utils.couch.database import iter_docs

from corehq.apps.groups.models import Group
from corehq.warehouse.const import GROUP_DIM_SLUG, GROUP_STAGING_SLUG
from corehq.warehouse.dbaccessors import get_group_ids_by_last_modified
from corehq.warehouse.etl import CustomSQLETLMixin, HQToWarehouseETLMixin
from corehq.warehouse.loaders.base import BaseLoader, BaseStagingLoader
from corehq.warehouse.models import GroupDim, GroupStagingTable


class GroupStagingLoader(HQToWarehouseETLMixin, BaseStagingLoader):
    """
    Represents the staging table to dump data before loading into the GroupDim

    Grain: group_id
    """
    slug = GROUP_STAGING_SLUG
    model_cls = GroupStagingTable

    def field_mapping(self):
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

    def record_iter(self, start_datetime, end_datetime):
        group_ids = get_group_ids_by_last_modified(start_datetime, end_datetime)

        return iter_docs(Group.get_db(), group_ids)


class GroupDimLoader(CustomSQLETLMixin, BaseLoader):
    """
    Dimension for Groups

    Grain: group_id
    """
    slug = GROUP_DIM_SLUG
    model_cls = GroupDim

    def dependant_slugs(self):
        return [GROUP_STAGING_SLUG]
