from datetime import datetime

from celery.task import periodic_task
from celery.schedules import crontab

from corehq.blobs.models import BlobExpiration
from corehq.blobs import get_blob_db


@periodic_task(run_every=crontab(minute=0, hour='0,12'))
def delete_expired_blobs():
    blob_expirations = BlobExpiration.objects.filter(expires_on__lt=_utcnow(), deleted=False)

    db = get_blob_db()
    paths = []
    for blob_expiration in blob_expirations:
        paths.append(db.get_path(blob_expiration.identifier, blob_expiration.bucket))

    db.bulk_delete(paths)
    blob_expirations.update(deleted=True)


def _utcnow():
    return datetime.utcnow()
