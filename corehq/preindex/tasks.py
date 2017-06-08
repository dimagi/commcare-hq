from celery.schedules import crontab
from celery.task.base import periodic_task

from corehq.preindex.accessors import index_design_doc, get_preindex_designs


@periodic_task(run_every=crontab(minute=0), queue='background_queue')
def preindex_couch_views():
    for design in get_preindex_designs():
        index_design_doc(design)
