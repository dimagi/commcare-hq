from contextlib import closing

from django.db import models, transaction, connections

from dimagi.utils.couch.database import iter_docs

from corehq.sql_db.routers import db_for_read_write
from corehq.apps.groups.dbaccessors import get_group_ids_by_last_modified
from corehq.apps.groups.models import Group
from corehq.warehouse.utils import django_batch_records


class StagingTable(models.Model):

    class Meta:
        abstract = True

    @classmethod
    def raw_record_iter(cls, start_datetime, end_datetime):
        raise NotImplementedError

    @classmethod
    @transaction.atomic
    def stage_records(cls, start_dateime, end_datetime):
        cls.clear_records()
        record_iter = cls.raw_record_iter(start_dateime, end_datetime)

        django_batch_records(cls, record_iter, cls.FIELD_MAPPING)

    @classmethod
    def clear_records(cls):
        database = db_for_read_write(cls)
        with closing(connections[database].cursor()) as cursor:
            cursor.execute("TRUNCATE {}".format(cls._meta.db_table))


class GroupStagingTable(StagingTable):
    slug = 'group_staging'

    group_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)

    case_sharing = models.NullBooleanField()
    reporting = models.NullBooleanField()

    group_last_modified = models.DateTimeField(null=True)

    # Map source model fields to staging table fields
    # ( <source field>, <staging field> )
    FIELD_MAPPING = [
        ('_id', 'group_id'),
        ('name', 'name'),
        ('case_sharing', 'case_sharing'),
        ('reporting', 'reporting'),
        ('last_modified', 'group_last_modified'),
    ]

    @classmethod
    def raw_record_iter(cls, start_datetime, end_datetime):
        group_ids = get_group_ids_by_last_modified(start_datetime, end_datetime)

        return iter_docs(Group.get_db(), group_ids)
