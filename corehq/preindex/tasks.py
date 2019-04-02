from __future__ import absolute_import
from __future__ import unicode_literals

from celery.task.base import periodic_task

from corehq.preindex.accessors import index_design_doc, get_preindex_designs
from corehq.util.celery_utils import deserialize_run_every_setting
from corehq.util.decorators import serial_task
from django.conf import settings


couch_reindex_schedule = deserialize_run_every_setting(settings.COUCH_REINDEX_SCHEDULE)


@periodic_task(run_every=couch_reindex_schedule, queue=settings.CELERY_PERIODIC_QUEUE)
def run_continuous_indexing_task():
    preindex_couch_views.delay()


@serial_task('couch-continuous-indexing', timeout=60 * 60, queue=settings.CELERY_PERIODIC_QUEUE, max_retries=0)
def preindex_couch_views():
    for design in get_preindex_designs():
        index_design_doc(design)
