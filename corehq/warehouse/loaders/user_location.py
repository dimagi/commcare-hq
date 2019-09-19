from corehq.warehouse.const import (
    LOCATION_DIM_SLUG,
    USER_DIM_SLUG,
    USER_LOCATION_DIM_SLUG,
    USER_STAGING_SLUG,
)
from corehq.warehouse.etl import CustomSQLETLMixin
from corehq.warehouse.loaders.base import BaseLoader
from corehq.warehouse.models import UserLocationDim


class UserLocationDimLoader(CustomSQLETLMixin, BaseLoader):
    """
    Dimension for User and Location mapping

    Grain: user_id, location_id
    """
    # TODO: Write Update SQL Query
    slug = USER_LOCATION_DIM_SLUG
    model_cls = UserLocationDim

    def dependencies(self):
        return [USER_DIM_SLUG, LOCATION_DIM_SLUG, USER_STAGING_SLUG]
