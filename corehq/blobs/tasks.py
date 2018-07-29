from __future__ import absolute_import
from __future__ import unicode_literals

import logging
from datetime import datetime

from celery.task import periodic_task
from celery.schedules import crontab

from corehq.util.datadog.gauges import datadog_counter
from corehq.blobs.models import BlobExpiration
from corehq.blobs import get_blob_db

log = logging.getLogger(__name__)


@periodic_task(run_every=crontab(minute=0, hour='0,12'))
def delete_expired_blobs():
    blob_expirations = BlobExpiration.objects.filter(expires_on__lt=_utcnow(), deleted=False)

    db = get_blob_db()
    paths = []
    deleted_ids = []
    bytes_deleted = 0
    for blob_expiration in blob_expirations[:1000]:
        paths.append(db.get_path(blob_expiration.identifier, blob_expiration.bucket))
        deleted_ids.append(blob_expiration.id)
        bytes_deleted += blob_expiration.length

    db.bulk_delete(paths)
    log.info("deleted expired blobs: %r", paths)
    BlobExpiration.objects.filter(id__in=deleted_ids).delete()
    datadog_counter('commcare.temp_blobs.bytes_deleted', value=bytes_deleted)
    if blob_expirations.exists():
        delete_expired_blobs.delay()

    return bytes_deleted


def _utcnow():
    return datetime.utcnow()
