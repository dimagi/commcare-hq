from __future__ import absolute_import

from __future__ import unicode_literals
import sys

from celery.schedules import crontab
from celery.task import periodic_task
from celery.task import task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.db.models import Count

from corehq.apps.change_feed.data_sources import get_document_store
from corehq.util.datadog.gauges import datadog_gauge
from dimagi.utils.couch import release_lock
from dimagi.utils.couch.cache import cache_core
from dimagi.utils.logging import notify_error
from pillow_retry.models import PillowError
from pillowtop.exceptions import PillowNotFoundError
from pillowtop.utils import get_pillow_by_name

logger = get_task_logger(__name__)


@task(queue='pillow_retry_queue', ignore_result=True)
def process_pillow_retry(error_doc_id):
    try:
        error_doc = PillowError.objects.get(id=error_doc_id)
    except PillowError.DoesNotExist:
        return

    pillow_name_or_class = error_doc.pillow
    try:
        pillow = get_pillow_by_name(pillow_name_or_class)
    except PillowNotFoundError:
        pillow = None

    if not pillow:
        notify_error((
            "Could not find pillowtop class '%s' while attempting a retry. "
            "If this pillow was recently deleted then this will be automatically cleaned up eventually. "
            "If not, then this should be looked into."
        ) % pillow_name_or_class)
        try:
            error_doc.total_attempts = PillowError.multi_attempts_cutoff() + 1
            error_doc.save()
        finally:
            return

    change = error_doc.change_object
    try:
        change_metadata = change.metadata
        if change_metadata:
            document_store = get_document_store(
                data_source_type=change_metadata.data_source_type,
                data_source_name=change_metadata.data_source_name,
                domain=change_metadata.domain
            )
            change.document_store = document_store
        pillow.process_change(change)
    except Exception:
        ex_type, ex_value, ex_tb = sys.exc_info()
        error_doc.add_attempt(ex_value, ex_tb)
        error_doc.save()
    else:
        error_doc.delete()


@periodic_task(
    run_every=crontab(minute="*/15"),
    queue=settings.CELERY_PERIODIC_QUEUE,
)
def record_pillow_error_queue_size():
    data = PillowError.objects.values('pillow').annotate(num_errors=Count('id'))
    for row in data:
        datadog_gauge('commcare.pillowtop.errors', row['num_errors'], tags=[
            'pillow_name:%s' % row['pillow']
        ])
