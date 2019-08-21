from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
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


@quickcache([], timeout=60 * 60)
def get_warehouse_latest_modified_date(email_on_delay=False):
    """
    Return in minutes how fresh is the data of app_status warehouse model.
    """
    last_completed_app_status_batch = Batch.objects.filter(
        dag_slug='app_status_batch', completed_on__isnull=False
    ).order_by('completed_on').last()
    # The end_datetime of a batch is used to filter on forms by last_modified (received_on, edited_on, deleted_on)
    if not last_completed_app_status_batch:
        return datetime(2000, 1, 1)
    latest_date = last_completed_app_status_batch.end_datetime
    if email_on_delay:
        SMS_TEAM = ['{}@{}'.format('icds-sms-rule', 'dimagi.com')]
        _soft_assert = soft_assert(to=SMS_TEAM, send_to_ops=False)
        lag = (datetime.utcnow() - latest_date).total_seconds() / 60
        if lag > ACCEPTABLE_WAREHOUSE_LAG_IN_MINUTES:
            _soft_assert(False,
                "The weekly inactive SMS rule is skipped for this week. Warehouse lag is {} minutes"
                .format(str(lag))
            )
        else:
            _soft_assert(False, "The weekly inactive SMS rule is successfully triggered for this week")

    return latest_date
