from django.db import models

from corehq.warehouse.const import (
    APP_STATUS_FACT_SLUG,
    USER_DIM_SLUG,
    FORM_STAGING_SLUG,
    SYNCLOG_STAGING_SLUG,
)

from .dimensions import UserDim
from .shared import CustomSQLETLMixin


class ApplicationStatusFact(models.Model, CustomSQLETLMixin):
    '''
    Application Status Report Fact Table

    Grain: app_id, user_id
    '''
    slug = APP_STATUS_FACT_SLUG

    # app_dim = models.CharField(max_length=255)

    # TODO is CASCADE the functionality that we want?
    user_dim = models.ForeignKey(UserDim, on_delete=models.CASCADE)

    last_form_submission_date = models.DateTimeField(null=True)
    last_sync_log_date = models.DateTimeField(null=True)

    last_form_app_build_version = models.CharField(max_length=255)
    last_form_app_commcare_version = models.CharField(max_length=255)
    last_form_app_source = models.CharField(max_length=255)

    last_sync_log_app_build_version = models.CharField(max_length=255)
    last_sync_log_app_commcare_version = models.CharField(max_length=255)
    last_sync_log_app_source = models.CharField(max_length=255)

    @classmethod
    def dependencies(cls):
        return [
            USER_DIM_SLUG,
            FORM_STAGING_SLUG,
            SYNCLOG_STAGING_SLUG,
        ]
