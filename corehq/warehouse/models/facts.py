from __future__ import absolute_import
from django.db import models, transaction

from corehq.warehouse.const import (
    APP_STATUS_FACT_SLUG,
    FORM_FACT_SLUG,
    USER_DIM_SLUG,
    DOMAIN_DIM_SLUG,
    FORM_STAGING_SLUG,
    SYNCLOG_STAGING_SLUG,
    SYNCLOG_FACT_SLUG,
)

from .dimensions import UserDim, DomainDim
from corehq.form_processor.models import XFormInstanceSQL
from corehq.sql_db.routers import db_for_read_write
from corehq.util.test_utils import unit_testing_only
from corehq.warehouse.etl import CustomSQLETLMixin
from corehq.warehouse.models.shared import WarehouseTable
from corehq.warehouse.utils import truncate_records_for_cls


class BaseFact(models.Model, WarehouseTable):

    batch = models.ForeignKey(
        'Batch',
        on_delete=models.PROTECT,
    )

    @classmethod
    def commit(cls, batch):
        with transaction.atomic(using=db_for_read_write(cls)):
            cls.load(batch)
        return True

    class Meta(object):
        abstract = True

    @classmethod
    @unit_testing_only
    def clear_records(cls):
        truncate_records_for_cls(cls, cascade=True)


class FormFact(BaseFact, CustomSQLETLMixin):
    '''
    Contains all `XFormInstance`s

    Grain: form_id
    '''
    # TODO: Write Update SQL Query
    slug = FORM_FACT_SLUG

    form_id = models.CharField(max_length=255, unique=True)

    domain = models.CharField(max_length=255)
    app_id = models.CharField(max_length=255, null=True)
    xmlns = models.CharField(max_length=255)
    user_id = models.CharField(max_length=255, null=True)

    user_dim = models.ForeignKey(UserDim, on_delete=models.PROTECT)
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

    @classmethod
    def dependencies(cls):
        return [
            USER_DIM_SLUG,
            DOMAIN_DIM_SLUG,
            FORM_STAGING_SLUG,
        ]


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

    user_dim = models.ForeignKey(UserDim, on_delete=models.PROTECT)
    domain_dim = models.ForeignKey(DomainDim, on_delete=models.PROTECT)

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
    # TODO: Write Update SQL Query (currently there exists a placeholder)
    slug = APP_STATUS_FACT_SLUG

    # TODO: Add app dimension
    # app_dim = models.CharField(max_length=255)

    # TODO: Add domain dimension
    # domain_dim = models.CharField(max_length=255)

    user_dim = models.ForeignKey(UserDim, on_delete=models.PROTECT)

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
            FORM_FACT_SLUG,
            SYNCLOG_STAGING_SLUG,
            SYNCLOG_FACT_SLUG,
        ]
