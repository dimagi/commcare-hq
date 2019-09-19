from corehq.warehouse.const import (
    APP_STATUS_FACT_SLUG,
    APP_STATUS_FORM_STAGING_SLUG,
    APP_STATUS_SYNCLOG_STAGING_SLUG,
    APPLICATION_DIM_SLUG,
    DOMAIN_DIM_SLUG,
    FORM_STAGING_SLUG,
    SYNCLOG_STAGING_SLUG,
    USER_DIM_SLUG,
)
from corehq.warehouse.etl import CustomSQLETLMixin
from corehq.warehouse.loaders.base import BaseDimLoader, BaseStagingLoader
from corehq.warehouse.models import (
    AppStatusFormStaging,
    AppStatusSynclogStaging,
)


class AppStatusFormStagingLoader(BaseStagingLoader, CustomSQLETLMixin):
    slug = APP_STATUS_FORM_STAGING_SLUG
    model_cls = AppStatusFormStaging

    @classmethod
    def dependencies(cls):
        return [
            FORM_STAGING_SLUG,
            APP_STATUS_FACT_SLUG,
            APPLICATION_DIM_SLUG,
            USER_DIM_SLUG,
            DOMAIN_DIM_SLUG
        ]


class AppStatusSynclogStagingLoader(BaseStagingLoader, CustomSQLETLMixin):
    slug = APP_STATUS_SYNCLOG_STAGING_SLUG
    model_cls = AppStatusSynclogStaging

    @classmethod
    def dependencies(cls):
        return [
            SYNCLOG_STAGING_SLUG,
            APP_STATUS_FACT_SLUG,
            APPLICATION_DIM_SLUG,
            USER_DIM_SLUG,
            DOMAIN_DIM_SLUG
        ]


class ApplicationStatusFactLoader(BaseDimLoader, CustomSQLETLMixin):
    """
    Application Status Report Fact Table

    Grain: app_id, user_id
    """
    slug = APP_STATUS_FACT_SLUG

    @classmethod
    def dependencies(cls):
        return [
            APP_STATUS_SYNCLOG_STAGING_SLUG,
            APP_STATUS_FORM_STAGING_SLUG,
        ]
