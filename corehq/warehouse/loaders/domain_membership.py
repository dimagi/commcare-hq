from corehq.warehouse.const import (
    DOMAIN_MEMBERSHIP_DIM_SLUG,
    USER_DIM_SLUG,
    USER_STAGING_SLUG,
)
from corehq.warehouse.etl import CustomSQLETLMixin
from corehq.warehouse.loaders.base import BaseLoader
from corehq.warehouse.models import DomainMembershipDim


class DomainMembershipDimLoader(CustomSQLETLMixin, BaseLoader):
    """
    Dimension for domain memberships for Web/CommCare users
    """
    slug = DOMAIN_MEMBERSHIP_DIM_SLUG
    model_cls = DomainMembershipDim

    def dependencies(self):
        return [USER_STAGING_SLUG, USER_DIM_SLUG]
