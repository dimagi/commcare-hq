from __future__ import absolute_import
from __future__ import unicode_literals
from django.db import connections
from django.conf import settings

from corehq.warehouse.const import DJANGO_MAX_BATCH_SIZE
from corehq.sql_db.routers import db_for_read_write


def django_batch_records(cls, record_iter, field_mapping, batch_id):
    records = []
    for index, raw_record in enumerate(record_iter):
        record = {'batch_id': batch_id}
        for source_key, destination_key in field_mapping:
            if isinstance(raw_record, dict):
                record[destination_key] = raw_record.get(source_key)
            else:
                record[destination_key] = getattr(raw_record, source_key, None)

        records.append(cls(**record))

    cls.objects.bulk_create(records, batch_size=DJANGO_MAX_BATCH_SIZE)


def truncate_records_for_cls(cls, cascade=False):
    if settings.UNIT_TESTING:
        cls.objects.all().delete()
        return
    database = db_for_read_write(cls)
    with connections[database].cursor() as cursor:
        cursor.execute("TRUNCATE {} {}".format(cls._meta.db_table, 'CASCADE' if cascade else ''))
