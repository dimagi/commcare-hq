from django.db import models, transaction

from dimagi.utils.couch.database import iter_docs

from corehq.apps.groups.dbaccessors import get_group_ids_by_last_modified
from corehq.apps.groups.models import Group


class StagingTable(models.Model):

    staged_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    @classmethod
    def stage_records(cls, start_dateime, end_datetime):
        raise NotImplementedError

    @classmethod
    def raw_record_iter(cls, start_datetime, end_datetime):
        raise NotImplementedError

    @classmethod
    def clear_records(cls):
        raise NotImplementedError


class GroupStagingTable(StagingTable):
    slug = 'group_staging'

    group_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)

    case_sharing = models.NullBooleanField()
    reporting = models.NullBooleanField()

    group_last_modified = models.DateTimeField(null=True)

    @classmethod
    @transaction.atomic
    def stage_records(cls, start_dateime, end_datetime):
        cls.clear_records()

        records = []
        for raw_record in cls.raw_record_iter(start_dateime, end_datetime):
            records.append(GroupStagingTable(
                group_id=raw_record.get('_id'),
                name=raw_record.get('name'),
                case_sharing=raw_record.get('case_sharing'),
                reporting=raw_record.get('reporting'),
                group_last_modified=raw_record.get('last_modified'),
            ))
        cls.objects.bulk_create(records)

    @classmethod
    def raw_record_iter(cls, start_datetime, end_datetime):
        group_ids = get_group_ids_by_last_modified(start_datetime, end_datetime)

        return iter_docs(Group.get_db(), group_ids)

    @classmethod
    def clear_records(cls):
        cls.objects.all().delete()
