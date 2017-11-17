from __future__ import absolute_import
from datetime import datetime

from celery.task import periodic_task
from celery.schedules import crontab

from corehq.util.datadog.gauges import datadog_counter
from corehq.blobs.models import BlobExpiration
from corehq.blobs import get_blob_db


@periodic_task(run_every=crontab(minute=0, hour='0,12'))
def delete_expired_blobs():
    blob_expirations = BlobExpiration.objects.filter(expires_on__lt=_utcnow(), deleted=False)

    db = get_blob_db()
    paths = []
    bytes_deleted = 0
    for blob_expiration in blob_expirations:
        paths.append(db.get_path(blob_expiration.identifier, blob_expiration.bucket))
        bytes_deleted += blob_expiration.length

    db.bulk_delete(paths)
    blob_expirations.update(deleted=True)
    datadog_counter(
        'commcare.temp_blobs.bytes_deleted',
        value=bytes_deleted,
    )
    return bytes_deleted


def _utcnow():
    return datetime.utcnow()
