from dimagi.utils.couch.database import iter_docs

from corehq.apps.users.models import CouchUser
from corehq.warehouse.const import USER_DIM_SLUG, USER_STAGING_SLUG
from corehq.warehouse.dbaccessors import get_user_ids_by_last_modified
from corehq.warehouse.etl import CustomSQLETLMixin, HQToWarehouseETLMixin
from corehq.warehouse.loaders.base import BaseLoader, BaseStagingLoader
from corehq.warehouse.models import UserDim, UserStagingTable


class UserStagingLoader(HQToWarehouseETLMixin, BaseStagingLoader):
    """
    Represents the staging table to dump data before loading into the UserDim

    Grain: user_id
    """
    slug = USER_STAGING_SLUG
    model_cls = UserStagingTable

    def field_mapping(self):
        return [
            ('_id', 'user_id'),
            ('username', 'username'),
            ('first_name', 'first_name'),
            ('last_name', 'last_name'),
            ('email', 'email'),
            ('domain', 'domain'),
            ('doc_type', 'doc_type'),
            ('base_doc', 'base_doc'),
            ('is_active', 'is_active'),
            ('is_staff', 'is_staff'),
            ('is_superuser', 'is_superuser'),
            ('last_login', 'last_login'),
            ('date_joined', 'date_joined'),
            ('last_modified', 'user_last_modified'),
            ('domain_memberships', 'domain_memberships'),
            ('assigned_location_ids', 'assigned_location_ids')
        ]

    def record_iter(self, start_datetime, end_datetime):
        user_ids = get_user_ids_by_last_modified(start_datetime, end_datetime)

        return iter_docs(CouchUser.get_db(), user_ids)


class UserDimLoader(CustomSQLETLMixin, BaseLoader):
    """
    Dimension for Users

    Grain: user_id
    """
    slug = USER_DIM_SLUG
    model_cls = UserDim

    def dependant_slugs(self):
        return [USER_STAGING_SLUG]
