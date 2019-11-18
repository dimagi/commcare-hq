from django.db import connections
from django.conf import settings
from datetime import datetime

from dimagi.utils.chunked import chunked

from corehq.warehouse.models.meta import Batch
from corehq.warehouse.const import DJANGO_MAX_BATCH_SIZE
from corehq.sql_db.routers import db_for_read_write
from corehq.util.quickcache import quickcache
from corehq.util.soft_assert import soft_assert
from custom.icds.const import ACCEPTABLE_WAREHOUSE_LAG_IN_MINUTES


def django_batch_records(cls, record_iter, field_mapping, batch_id):
    for batch in chunked(record_iter, DJANGO_MAX_BATCH_SIZE):
        records = []
        for raw_record in batch:
            record = {'batch_id': batch_id}
            for source_key, destination_key in field_mapping:
                value = raw_record
                for key in source_key.split('.'):
                    if isinstance(raw_record, dict):
                        value = value.get(key)
                    else:
                        value = getattr(value, key, None)
                record[destination_key] = value

            records.append(cls(**record))

        cls.objects.bulk_create(records, batch_size=DJANGO_MAX_BATCH_SIZE)


def truncate_records_for_cls(cls, cascade=False):
    if settings.UNIT_TESTING:
        cls.objects.all().delete()
        return
    database = db_for_read_write(cls)
    with connections[database].cursor() as cursor:
        cursor.execute("TRUNCATE {} {}".format(cls._meta.db_table, 'CASCADE' if cascade else ''))


class ProgressIterator(object):
    def __init__(self, tracker, iterable):
        self.__iterable = iter(iterable)
        self.tracker = tracker
        self.count = 0
        self.complete = False

    def __iter__(self):
        return self

    def __next__(self):
        try:
            value = next(self.__iterable)
            self.tracker.report_progress()
            return value
        except StopIteration:
            if not self.complete:  # prevent repeated calls
                self.complete = True
                self.tracker.complete()
            raise
