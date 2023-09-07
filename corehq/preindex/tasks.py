from django.conf import settings

from corehq.apps.celery import periodic_task
from corehq.preindex.accessors import get_preindex_designs, index_design_doc
from corehq.util.celery_utils import deserialize_run_every_setting
from corehq.util.decorators import serial_task

couch_reindex_schedule = deserialize_run_every_setting(settings.COUCH_REINDEX_SCHEDULE)


@periodic_task(run_every=couch_reindex_schedule, queue=settings.CELERY_PERIODIC_QUEUE)
def run_continuous_indexing_task():
    """
    prevent infrequently queried views from being very slow
    and keep stale=true queries reasonably fresh
    """
    preindex_couch_views.delay()


@serial_task('couch-continuous-indexing', timeout=60 * 60, queue=settings.CELERY_PERIODIC_QUEUE, max_retries=0)
def preindex_couch_views():
    for design in get_preindex_designs():
        index_design_doc(design)
