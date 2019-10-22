from corehq.warehouse.const import (
    GROUP_DIM_SLUG,
    GROUP_STAGING_SLUG,
    USER_DIM_SLUG,
    USER_GROUP_DIM_SLUG,
)
from corehq.warehouse.etl import CustomSQLETLMixin
from corehq.warehouse.loaders.base import BaseLoader
from corehq.warehouse.models import UserGroupDim


class UserGroupDimLoader(CustomSQLETLMixin, BaseLoader):
    """
    Dimension for User and Group mapping

    Grain: user_id, group_id
    """
    slug = USER_GROUP_DIM_SLUG
    model_cls = UserGroupDim

    def dependant_slugs(self):
        return [USER_DIM_SLUG, GROUP_DIM_SLUG, GROUP_STAGING_SLUG]
