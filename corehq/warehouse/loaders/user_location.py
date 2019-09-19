from corehq.warehouse.const import (
    LOCATION_DIM_SLUG,
    USER_DIM_SLUG,
    USER_LOCATION_DIM_SLUG,
    USER_STAGING_SLUG,
)
from corehq.warehouse.etl import CustomSQLETLMixin
from corehq.warehouse.loaders.base import BaseDimLoader
from corehq.warehouse.models import UserLocationDim


class UserLocationDimLoader(BaseDimLoader, CustomSQLETLMixin):
    """
    Dimension for User and Location mapping

    Grain: user_id, location_id
    """
    # TODO: Write Update SQL Query
    slug = USER_LOCATION_DIM_SLUG
    model_cls = UserLocationDim

    @classmethod
    def dependencies(cls):
        return [USER_DIM_SLUG, LOCATION_DIM_SLUG, USER_STAGING_SLUG]
