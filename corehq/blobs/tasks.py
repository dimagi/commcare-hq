from __future__ import absolute_import
from __future__ import unicode_literals

import logging
from datetime import datetime

from celery.task import periodic_task
from celery.schedules import crontab

from corehq.util.datadog.gauges import datadog_counter
from corehq.blobs.models import BlobMeta
from corehq.blobs import get_blob_db
from corehq.sql_db.util import get_db_aliases_for_partitioned_query

log = logging.getLogger(__name__)


@periodic_task(run_every=crontab(minute=0, hour='0,12'))
def delete_expired_blobs():
    run_again = False
    bytes_deleted = 0
    for dbname in get_db_aliases_for_partitioned_query():
        expired = list(BlobMeta.objects.using(dbname).filter(
            expires_on__isnull=False,
            expires_on__lt=_utcnow(),
        )[:1000])
        if not expired:
            continue
        if len(expired) == 1000:
            run_again = True
        get_blob_db().bulk_delete(metas=expired)
        log.info("deleted expired blobs: %r", [m.key for m in expired])
        shard_deleted = sum(m.content_length for m in expired)
        bytes_deleted += shard_deleted
        datadog_counter('commcare.temp_blobs.bytes_deleted', value=shard_deleted)

    if run_again:
        delete_expired_blobs.delay()

    return bytes_deleted


def _utcnow():
    return datetime.utcnow()
