from celery.schedules import crontab
from celery.task import periodic_task
from django.conf import settings
from django.db.models import Count

from corehq.util.metrics import metrics_gauge
from pillow_retry.models import PillowError


@periodic_task(
    run_every=crontab(minute="*/15"),
    queue=settings.CELERY_PERIODIC_QUEUE,
)
def record_pillow_error_queue_size():
    data = PillowError.objects.values('pillow').annotate(num_errors=Count('id'))
    for row in data:
        metrics_gauge('commcare.pillowtop.error_queue', row['num_errors'], tags={
            'pillow_name': row['pillow'],
            'host': 'celery',
            'group': 'celery'
        })
