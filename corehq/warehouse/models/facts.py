import architect

from django.db import models, transaction

from corehq.form_processor.models import XFormInstanceSQL
from corehq.sql_db.routers import db_for_read_write
from corehq.util.test_utils import unit_testing_only
from corehq.warehouse.const import (APPLICATION_DIM_SLUG, APP_STATUS_FACT_SLUG,
    DOMAIN_DIM_SLUG, FORM_FACT_SLUG, FORM_STAGING_SLUG, SYNCLOG_FACT_SLUG,
    SYNCLOG_STAGING_SLUG, USER_DIM_SLUG, APP_STATUS_FORM_STAGING_SLUG, APP_STATUS_SYNCLOG_STAGING_SLUG)
from corehq.warehouse.etl import CustomSQLETLMixin
from corehq.warehouse.models.dimensions import DomainDim, UserDim, ApplicationDim
from corehq.warehouse.models.shared import WarehouseTable
from corehq.warehouse.utils import truncate_records_for_cls


class BaseFact(models.Model):
    batch = models.ForeignKey(
        'Batch',
        on_delete=models.PROTECT,
    )

    class Meta(object):
        abstract = True


@architect.install('partition', type='range', subtype='date', constraint='month', column='received_on')
class FormFact(BaseFact):
    """
    Contains all `XFormInstance`s

    Grain: form_id
    """
    form_id = models.CharField(max_length=255, unique=True)

    domain = models.CharField(max_length=255)
    app_id = models.CharField(max_length=255, null=True)
    xmlns = models.CharField(max_length=255)
    user_id = models.CharField(max_length=255, null=True)

    user_dim = models.ForeignKey(UserDim, on_delete=models.PROTECT, null=True)
    domain_dim = models.ForeignKey(DomainDim, on_delete=models.PROTECT)

    # The time at which the server has received the form
    received_on = models.DateTimeField(db_index=True)
    deleted_on = models.DateTimeField(null=True)
    edited_on = models.DateTimeField(null=True)
    last_modified = models.DateTimeField(null=True)

    time_end = models.DateTimeField(null=True, blank=True)
    time_start = models.DateTimeField(null=True, blank=True)
    commcare_version = models.CharField(max_length=8, blank=True, null=True)
    app_version = models.PositiveIntegerField(null=True, blank=True)

    build_id = models.CharField(max_length=255, null=True)
    state = models.PositiveSmallIntegerField(
        choices=XFormInstanceSQL.STATES,
    )


class SyncLogFact(BaseFact, CustomSQLETLMixin):
    '''
    SyncLog Fact Table
    Grain: sync_log_id
    '''
    slug = SYNCLOG_FACT_SLUG

    sync_log_id = models.CharField(max_length=255)
    sync_date = models.DateTimeField(null=True)

    # these can be null per SyncLogStagingTable
    domain = models.CharField(max_length=255, null=True)

    user_dim = models.OneToOneField(UserDim, on_delete=models.PROTECT)
    # not all synclogs have domains, added in 11/2016
    domain_dim = models.ForeignKey(DomainDim, on_delete=models.PROTECT, null=True)

    # these can be null per SyncLogStagingTable
    build_id = models.CharField(max_length=255, null=True)

    duration = models.IntegerField(null=True)  # in seconds

    @classmethod
    def dependencies(cls):
        return [
            USER_DIM_SLUG,
            DOMAIN_DIM_SLUG,
            SYNCLOG_STAGING_SLUG,
        ]


class ApplicationStatusFact(BaseFact, CustomSQLETLMixin):
    '''
    Application Status Report Fact Table

    Grain: app_id, user_id
    '''
    slug = APP_STATUS_FACT_SLUG

    app_dim = models.ForeignKey(ApplicationDim, on_delete=models.PROTECT, null=True)

    domain = models.CharField(max_length=255, db_index=True)

    user_dim = models.ForeignKey(UserDim, on_delete=models.PROTECT)

    last_form_submission_date = models.DateTimeField(null=True)
    last_sync_log_date = models.DateTimeField(null=True)

    last_form_app_build_version = models.CharField(max_length=255, null=True)
    last_form_app_commcare_version = models.CharField(max_length=255, null=True)

    @classmethod
    def dependencies(cls):
        return [
            APP_STATUS_SYNCLOG_STAGING_SLUG,
            APP_STATUS_FORM_STAGING_SLUG,
        ]
