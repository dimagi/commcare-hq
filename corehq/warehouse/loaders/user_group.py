from corehq.warehouse.const import (
    GROUP_DIM_SLUG,
    GROUP_STAGING_SLUG,
    USER_DIM_SLUG,
    USER_GROUP_DIM_SLUG,
)
from corehq.warehouse.etl import CustomSQLETLMixin
from corehq.warehouse.loaders.base import BaseLoader


class UserGroupDimLoader(BaseLoader, CustomSQLETLMixin):
    """
    Dimension for User and Group mapping

    Grain: user_id, group_id
    """
    slug = USER_GROUP_DIM_SLUG

    @classmethod
    def dependencies(cls):
        return [USER_DIM_SLUG, GROUP_DIM_SLUG, GROUP_STAGING_SLUG]
