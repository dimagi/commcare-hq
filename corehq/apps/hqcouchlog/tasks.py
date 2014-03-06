from datetime import timedelta, datetime
from celery.schedules import crontab
from celery.task.base import periodic_task
from couchlog.models import ExceptionRecord
from django.conf import settings

@periodic_task(run_every=crontab(minute=0, hour=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def purge_old_logs():
    key = datetime.now() - timedelta(weeks=52)
    results = ExceptionRecord.view(
        "couchlog/all_by_date",
        reduce=False,
        startkey=[key.isoformat()],
        descending=True,
        limit=1000,
        include_docs=False)

    db = ExceptionRecord.get_db()
    docs = []
    for result in results:
        docs.append({
            '_id': result['id'],
            '_rev': db.get_rev(result['id']),
            '_deleted': True,
        })

    db.bulk_save(docs, use_uuids=False)