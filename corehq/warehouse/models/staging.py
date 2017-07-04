from contextlib import closing

from django.db import models, transaction, connections

from dimagi.utils.couch.database import iter_docs

from corehq.sql_db.routers import db_for_read_write
from corehq.apps.users.models import CouchUser
from corehq.apps.groups.models import Group
from corehq.apps.domain.models import Domain
from corehq.warehouse.dbaccessors import (
    get_group_ids_by_last_modified,
    get_user_ids_by_last_modified,
    get_domain_ids_by_last_modified,
)
from corehq.warehouse.utils import django_batch_records


class StagingTable(models.Model):

    class Meta:
        abstract = True

    @classmethod
    def raw_record_iter(cls, start_datetime, end_datetime):
        raise NotImplementedError

    @classmethod
    def field_mapping(cls):
        # Map source model fields to staging table fields
        # ( <source field>, <staging field> )
        raise NotImplementedError

    @classmethod
    @transaction.atomic
    def stage_records(cls, start_dateime, end_datetime):
        cls.clear_records()
        record_iter = cls.raw_record_iter(start_dateime, end_datetime)

        django_batch_records(cls, record_iter, cls.field_mapping())

    @classmethod
    def clear_records(cls):
        database = db_for_read_write(cls)
        with closing(connections[database].cursor()) as cursor:
            cursor.execute("TRUNCATE {}".format(cls._meta.db_table))


class GroupStagingTable(StagingTable):
    slug = 'group_staging'

    group_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    doc_type = models.CharField(max_length=100)

    case_sharing = models.NullBooleanField()
    reporting = models.NullBooleanField()

    group_last_modified = models.DateTimeField(null=True)

    @classmethod
    def field_mapping(cls):
        return [
            ('_id', 'group_id'),
            ('name', 'name'),
            ('case_sharing', 'case_sharing'),
            ('reporting', 'reporting'),
            ('last_modified', 'group_last_modified'),
            ('doc_type', 'doc_type'),
        ]

    @classmethod
    def raw_record_iter(cls, start_datetime, end_datetime):
        group_ids = get_group_ids_by_last_modified(start_datetime, end_datetime)

        return iter_docs(Group.get_db(), group_ids)


class UserStagingTable(StagingTable):
    slug = 'user_staging'

    user_id = models.CharField(max_length=255)
    username = models.CharField(max_length=150)
    first_name = models.CharField(max_length=30, null=True)
    last_name = models.CharField(max_length=30, null=True)
    email = models.CharField(max_length=255, null=True)
    doc_type = models.CharField(max_length=100)
    base_doc = models.CharField(max_length=100)

    is_active = models.BooleanField()
    is_staff = models.BooleanField()
    is_superuser = models.BooleanField()

    last_login = models.DateTimeField(null=True)
    date_joined = models.DateTimeField()

    user_last_modified = models.DateTimeField(null=True)

    @classmethod
    def field_mapping(cls):
        return [
            ('_id', 'user_id'),
            ('username', 'username'),
            ('first_name', 'first_name'),
            ('last_name', 'last_name'),
            ('email', 'email'),
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
    def raw_record_iter(cls, start_datetime, end_datetime):
        user_ids = get_user_ids_by_last_modified(start_datetime, end_datetime)

        return iter_docs(CouchUser.get_db(), user_ids)


class DomainStagingTable(StagingTable):
    slug = 'domain_staging'

    domain_id = models.CharField(max_length=255)
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

    domain_last_modified = models.DateTimeField()
    domain_created_on = models.DateTimeField(null=True)

    @classmethod
    def field_mapping(cls):
        return [
            ('_id', 'domain_id'),
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
    def raw_record_iter(cls, start_datetime, end_datetime):
        domain_ids = get_domain_ids_by_last_modified(start_datetime, end_datetime)

        return iter_docs(Domain.get_db(), domain_ids)
