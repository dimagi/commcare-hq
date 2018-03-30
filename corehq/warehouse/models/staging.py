from __future__ import absolute_import
from __future__ import unicode_literals
from contextlib import closing

from django.db import models, transaction, connections
from django.contrib.postgres.fields import ArrayField

from dimagi.utils.couch.database import iter_docs

from corehq.sql_db.routers import db_for_read_write
from corehq.apps.app_manager.models import Application
from corehq.apps.users.models import CouchUser
from corehq.apps.groups.models import Group
from corehq.apps.domain.models import Domain
from casexml.apps.phone.models import SyncLog
from corehq.form_processor.models import XFormInstanceSQL
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.warehouse.dbaccessors import (
    get_group_ids_by_last_modified,
    get_user_ids_by_last_modified,
    get_domain_ids_by_last_modified,
    get_synclog_ids_by_date,
    get_forms_by_last_modified,
    get_application_ids_by_last_modified
)
from corehq.warehouse.const import (
    GROUP_STAGING_SLUG,
    USER_STAGING_SLUG,
    DOMAIN_STAGING_SLUG,
    FORM_STAGING_SLUG,
    SYNCLOG_STAGING_SLUG,
    LOCATION_STAGING_SLUG,
    LOCATION_TYPE_STAGING_SLUG,
    APPLICATION_STAGING_SLUG
)

from corehq.warehouse.utils import truncate_records_for_cls
from corehq.warehouse.models.shared import WarehouseTable
from corehq.warehouse.etl import CouchToDjangoETLMixin, CustomSQLETLMixin


class StagingTable(models.Model, WarehouseTable):
    batch = models.ForeignKey(
        'Batch',
        on_delete=models.PROTECT,
    )

    class Meta(object):
        abstract = True

    @classmethod
    def commit(cls, batch):
        cls.clear_records()
        cls.load(batch)
        return True

    @classmethod
    def clear_records(cls):
        truncate_records_for_cls(cls, cascade=False)


class LocationStagingTable(StagingTable, CustomSQLETLMixin):
    '''
    Represents the staging table to dump data before loading into the LocationDim

    Grain: location_id
    '''
    slug = LOCATION_STAGING_SLUG

    domain = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    site_code = models.CharField(max_length=100)
    location_id = models.CharField(max_length=255)
    location_type_id = models.IntegerField()
    external_id = models.CharField(max_length=255, null=True)
    supply_point_id = models.CharField(max_length=255, null=True)
    user_id = models.CharField(max_length=255)

    sql_location_id = models.IntegerField()
    sql_parent_location_id = models.IntegerField(null=True)

    location_last_modified = models.DateTimeField(null=True)
    location_created_on = models.DateTimeField(null=True)

    is_archived = models.NullBooleanField()

    latitude = models.DecimalField(max_digits=20, decimal_places=10, null=True)
    longitude = models.DecimalField(max_digits=20, decimal_places=10, null=True)

    @classmethod
    def dependencies(cls):
        return []

    @classmethod
    def additional_sql_context(cls):
        return {
            'sqllocation_table': SQLLocation._meta.db_table
        }


class LocationTypeStagingTable(StagingTable, CustomSQLETLMixin):
    '''
    Represents the staging table to dump data before loading into the LocationDim

    Grain: location_type_id
    '''
    slug = LOCATION_TYPE_STAGING_SLUG

    domain = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    code = models.SlugField(db_index=False, null=True)
    location_type_id = models.IntegerField()

    location_type_last_modified = models.DateTimeField(null=True)

    @classmethod
    def dependencies(cls):
        return []

    @classmethod
    def additional_sql_context(cls):
        return {
            'locationtype_table': LocationType._meta.db_table
        }


class GroupStagingTable(StagingTable, CouchToDjangoETLMixin):
    '''
    Represents the staging table to dump data before loading into the GroupDim

    Grain: group_id
    '''
    slug = GROUP_STAGING_SLUG

    group_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    doc_type = models.CharField(max_length=100)
    domain = models.CharField(max_length=100)
    user_ids = ArrayField(models.CharField(max_length=255), null=True)
    removed_user_ids = ArrayField(models.CharField(max_length=255), null=True)

    case_sharing = models.NullBooleanField()
    reporting = models.NullBooleanField()

    group_last_modified = models.DateTimeField(null=True)

    @classmethod
    def field_mapping(cls):
        return [
            ('_id', 'group_id'),
            ('domain', 'domain'),
            ('name', 'name'),
            ('case_sharing', 'case_sharing'),
            ('reporting', 'reporting'),
            ('last_modified', 'group_last_modified'),
            ('doc_type', 'doc_type'),
            ('users', 'user_ids'),
            ('removed_users', 'removed_user_ids'),
        ]

    @classmethod
    def dependencies(cls):
        return []

    @classmethod
    def record_iter(cls, start_datetime, end_datetime):
        group_ids = get_group_ids_by_last_modified(start_datetime, end_datetime)

        return iter_docs(Group.get_db(), group_ids)


class UserStagingTable(StagingTable, CouchToDjangoETLMixin):
    '''
    Represents the staging table to dump data before loading into the UserDim

    Grain: user_id
    '''
    slug = USER_STAGING_SLUG

    user_id = models.CharField(max_length=255)
    username = models.CharField(max_length=150)
    first_name = models.CharField(max_length=30, null=True)
    last_name = models.CharField(max_length=30, null=True)
    email = models.CharField(max_length=255, null=True)
    doc_type = models.CharField(max_length=100)
    base_doc = models.CharField(max_length=100)
    domain = models.CharField(max_length=100)

    is_active = models.BooleanField()
    is_staff = models.BooleanField()
    is_superuser = models.BooleanField()

    last_login = models.DateTimeField(null=True)
    date_joined = models.DateTimeField()

    user_last_modified = models.DateTimeField(null=True)

    @classmethod
    def dependencies(cls):
        return []

    @classmethod
    def field_mapping(cls):
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
        ]

    @classmethod
    def record_iter(cls, start_datetime, end_datetime):
        user_ids = get_user_ids_by_last_modified(start_datetime, end_datetime)

        return iter_docs(CouchUser.get_db(), user_ids)


class DomainStagingTable(StagingTable, CouchToDjangoETLMixin):
    '''
    Represents the staging table to dump data before loading into the DomainDim

    Grain: domain_id
    '''
    slug = DOMAIN_STAGING_SLUG

    domain_id = models.CharField(max_length=255)
    domain = models.CharField(max_length=100)
    default_timezone = models.CharField(max_length=255)
    hr_name = models.CharField(max_length=255, null=True)
    creating_user_id = models.CharField(max_length=255, null=True)
    project_type = models.CharField(max_length=255, null=True)
    doc_type = models.CharField(max_length=100)

    is_active = models.BooleanField()
    case_sharing = models.BooleanField()
    commtrack_enabled = models.BooleanField()
    is_test = models.CharField(max_length=255)
    location_restriction_for_users = models.BooleanField()
    use_sql_backend = models.NullBooleanField()
    first_domain_for_user = models.NullBooleanField()

    domain_last_modified = models.DateTimeField(null=True)
    domain_created_on = models.DateTimeField(null=True)

    @classmethod
    def dependencies(cls):
        return []

    @classmethod
    def field_mapping(cls):
        return [
            ('_id', 'domain_id'),
            ('name', 'domain'),
            ('default_timezone', 'default_timezone'),
            ('hr_name', 'hr_name'),
            ('creating_user_id', 'creating_user_id'),
            ('project_type', 'project_type'),

            ('is_active', 'is_active'),
            ('case_sharing', 'case_sharing'),
            ('commtrack_enabled', 'commtrack_enabled'),
            ('is_test', 'is_test'),
            ('location_restriction_for_users', 'location_restriction_for_users'),
            ('use_sql_backend', 'use_sql_backend'),
            ('first_domain_for_user', 'first_domain_for_user'),

            ('last_modified', 'domain_last_modified'),
            ('date_created', 'domain_created_on'),
            ('doc_type', 'doc_type'),
        ]

    @classmethod
    def record_iter(cls, start_datetime, end_datetime):
        domain_ids = get_domain_ids_by_last_modified(start_datetime, end_datetime)

        return iter_docs(Domain.get_db(), domain_ids)


class FormStagingTable(StagingTable, CouchToDjangoETLMixin):
    '''
    Represents the staging table to dump data before loading into the FormFact

    Grain: form_id
    '''
    slug = FORM_STAGING_SLUG

    form_id = models.CharField(max_length=255, unique=True)

    domain = models.CharField(max_length=255, default=None)
    app_id = models.CharField(max_length=255, null=True)
    xmlns = models.CharField(max_length=255, default=None)
    user_id = models.CharField(max_length=255, null=True)

    # The time at which the server has received the form
    received_on = models.DateTimeField(db_index=True)
    deleted_on = models.DateTimeField(null=True)
    edited_on = models.DateTimeField(null=True)

    build_id = models.CharField(max_length=255, null=True)

    state = models.PositiveSmallIntegerField(
        choices=XFormInstanceSQL.STATES,
        default=XFormInstanceSQL.NORMAL
    )

    @classmethod
    def dependencies(cls):
        return []

    @classmethod
    def field_mapping(cls):
        return [
            ('form_id', 'form_id'),
            ('domain', 'domain'),
            ('app_id', 'app_id'),
            ('xmlns', 'xmlns'),
            ('user_id', 'user_id'),

            ('received_on', 'received_on'),
            ('deleted_on', 'deleted_on'),
            ('edited_on', 'edited_on'),
            ('build_id', 'build_id'),
        ]

    @classmethod
    def record_iter(cls, start_datetime, end_datetime):
        return get_forms_by_last_modified(start_datetime, end_datetime)


class SyncLogStagingTable(StagingTable, CouchToDjangoETLMixin):
    '''
    Represents the staging table to dump data before loading into the SyncLogFact

    Grain: sync_log_id
    '''
    slug = SYNCLOG_STAGING_SLUG

    sync_log_id = models.CharField(max_length=255)
    sync_date = models.DateTimeField(null=True)

    # this is only added as of 11/2016 - not guaranteed to be set
    domain = models.CharField(max_length=255, null=True)
    user_id = models.CharField(max_length=255, null=True)

    # this is only added as of 11/2016 and only works with app-aware sync
    build_id = models.CharField(max_length=255, null=True)

    duration = models.IntegerField(null=True)  # in seconds

    @classmethod
    def dependencies(cls):
        return []

    @classmethod
    def field_mapping(cls):
        return [
            ('_id', 'sync_log_id'),
            ('date', 'sync_date'),
            ('domain', 'domain'),
            ('user_id', 'user_id'),
            ('build_id', 'build_id'),
            ('duration', 'duration'),
        ]

    @classmethod
    def record_iter(cls, start_datetime, end_datetime):
        synclog_ids = get_synclog_ids_by_date(start_datetime, end_datetime)
        return iter_docs(SyncLog.get_db(), synclog_ids)


class ApplicationStagingTable(StagingTable, CouchToDjangoETLMixin):
    '''
    Represents the staging table to dump data before loading into the ApplicationDim

    Grain: application_id
    '''
    slug = APPLICATION_STAGING_SLUG

    application_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=100)
    application_last_modified = models.DateTimeField(null=True)
    doc_type = models.CharField(max_length=100)

    @classmethod
    def field_mapping(cls):
        return [
            ('_id', 'application_id'),
            ('domain', 'domain'),
            ('name', 'name'),
            ('last_modified', 'application_last_modified'),
            ('doc_type', 'doc_type')
        ]

    @classmethod
    def dependencies(cls):
        return []

    @classmethod
    def record_iter(cls, start_datetime, end_datetime):
        application_ids = get_application_ids_by_last_modified(start_datetime, end_datetime)

        return iter_docs(Application.get_db(), application_ids)
