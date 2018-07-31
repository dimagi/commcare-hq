from __future__ import absolute_import
from __future__ import unicode_literals
from django.db import connections
from django.conf import settings

from dimagi.utils.chunked import chunked

from corehq.warehouse.const import DJANGO_MAX_BATCH_SIZE
from corehq.sql_db.routers import db_for_read_write


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
