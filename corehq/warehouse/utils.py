from __future__ import absolute_import
from __future__ import unicode_literals
from django.db import connections
from django.conf import settings

from dimagi.utils.chunked import chunked

from corehq.warehouse.models.meta import Batch
from corehq.warehouse.const import DJANGO_MAX_BATCH_SIZE
from corehq.sql_db.routers import db_for_read_write
from corehq.util.quickcache import quickcache


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


@quickcache([], timeout=60 * 60)
def get_warehouse_latest_modified_date():
    """
    Return in minutes how fresh is the data of app_status warehouse model.
    """
    last_completed_app_status_batch = Batch.objects.filter(
        dag_slug='app_status_batch', completed_on__isnull=False
    ).order_by('completed_on').last()
    # The end_datetime of a batch is used to filter on forms by last_modified (received_on, edited_on, deleted_on)
    return last_completed_app_status_batch.end_datetime
