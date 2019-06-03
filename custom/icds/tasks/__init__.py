from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import timedelta, datetime
from celery.schedules import crontab
from celery.task import periodic_task
from django.conf import settings
from corehq.blobs import get_blob_db, CODES
from corehq.blobs.models import BlobMeta
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.util.datadog.gauges import datadog_counter
from custom.icds.tasks.hosted_ccz import (
    setup_ccz_file_for_hosting,
)

if settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS:
    @periodic_task(run_every=crontab(minute=0, hour='22'))
    def delete_old_images(cutoff=None):
        cutoff = cutoff or datetime.utcnow()
        max_age = cutoff - timedelta(days=90)
        db = get_blob_db()

        def _get_query(db_name, max_age=max_age):
            return BlobMeta.objects.using(db_name).filter(
                content_type='image/jpeg',
                type_code=CODES.form_attachment,
                domain='icds-cas',
                created_on__lt=max_age
            )

        run_again = False
        for db_name in get_db_aliases_for_partitioned_query():
            bytes_deleted = 0
            metas = list(_get_query(db_name)[:1000])
            if metas:
                for meta in metas:
                    bytes_deleted += meta.content_length or 0
                db.bulk_delete(metas=metas)
                datadog_counter('commcare.icds_images.bytes_deleted', value=bytes_deleted)
                datadog_counter('commcare.icds_images.count_deleted', value=len(metas))
                run_again = True

        if run_again:
            delete_old_images.delay(cutoff)
