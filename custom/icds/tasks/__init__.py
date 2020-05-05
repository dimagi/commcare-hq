from datetime import datetime, timedelta

from celery.schedules import crontab
from celery.task import task
from django.conf import settings
from iso8601 import parse_date

from corehq.blobs import CODES, get_blob_db
from corehq.blobs.models import BlobMeta
from corehq.sql_db.util import get_db_aliases_for_partitioned_query, estimate_row_count
from corehq.util.celery_utils import periodic_task_on_envs
from corehq.util.metrics import metrics_counter, metrics_gauge
from custom.icds.tasks.sms import send_monthly_sms_report  # noqa imported for celery
from custom.icds.tasks.hosted_ccz import setup_ccz_file_for_hosting  # noqa imported for celery

MAX_RUNTIME = 6 * 3600


@periodic_task_on_envs(settings.ICDS_ENVS, run_every=crontab(minute=30, hour=18))
def delete_old_images():
    for db_name in get_db_aliases_for_partitioned_query():
        delete_old_images_on_db.delay(db_name, datetime.utcnow())


@task
def delete_old_images_on_db(db_name, cutoff):
    if isinstance(cutoff, str):
        cutoff = parse_date(cutoff, default_timezone=None)

    max_age = cutoff - timedelta(days=90)
    db = get_blob_db()

    def _get_query(db_name, max_age=max_age):
        return BlobMeta.objects.using(db_name).filter(
            type_code=CODES.form_attachment,
            domain='icds-cas',
            created_on__lt=max_age
        ).order_by('created_on')

    bytes_deleted = 0
    query = _get_query(db_name)
    metas = list(query[:1000])
    run_again = len(metas) == 1000
    if metas:
        for meta in metas:
            bytes_deleted += meta.content_length or 0
        db.bulk_delete(metas=metas)

        tags = {'database': db_name}
        age = datetime.utcnow() - metas[-1].created_on
        metrics_gauge('commcare.icds_images.max_age', value=age.total_seconds(), tags=tags)
        row_estimate = estimate_row_count(query, db_name)
        metrics_gauge('commcare.icds_images.count_estimate', value=row_estimate, tags=tags)
        metrics_counter('commcare.icds_images.bytes_deleted', value=bytes_deleted)
        metrics_counter('commcare.icds_images.count_deleted', value=len(metas))

    runtime = datetime.utcnow() - cutoff
    if run_again and runtime.total_seconds() < MAX_RUNTIME:
        delete_old_images_on_db.delay(db_name, cutoff)
