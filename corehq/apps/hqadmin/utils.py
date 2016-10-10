import json
from itertools import groupby

from django.conf import settings
from django.utils.safestring import mark_safe

from dimagi.utils.logging import notify_exception
from pillowtop.utils import force_seq_int, get_couch_pillow_instances
from restkit import Resource

from .models import PillowCheckpointSeqStore

EPSILON = 10000000


def pillow_seq_store():
    for pillow in get_couch_pillow_instances():
        checkpoint = pillow.checkpoint
        store, created = PillowCheckpointSeqStore.objects.get_or_create(checkpoint_id=checkpoint.checkpoint_id)
        db_seq = checkpoint.get_current_sequence_id()
        store_seq = force_seq_int(store.seq) or 0
        if not created and force_seq_int(db_seq) < store_seq - EPSILON:
            notify_exception(
                None,
                message='Found seq number lower than previous for {}. '
                        'This could mean we are in a rewind state'.format(store.checkpoint_id),
                details={
                    'pillow checkpoint seq': db_seq,
                    'stored seq': store.seq
                })
        else:
            store.seq = db_seq
            store.save()


def get_celery_stats():

    def get_stats(celery_monitoring, status_only=False, refresh=False):
        cresource = Resource(celery_monitoring, timeout=3)
        endpoint = "api/workers"
        params = {'refresh': 'true'} if refresh else {}
        if status_only:
            params['status'] = 'true'
        try:
            t = cresource.get(endpoint, params_dict=params).body_string()
            return json.loads(t)
        except Exception:
            return {}

    def get_task_html(detailed_stats, worker_name):
        tasks_ok = 'label-success'
        tasks_full = 'label-warning'

        tasks_html = mark_safe('<span class="label %s">unknown</span>' % tasks_full)
        try:
            worker_stats = detailed_stats[worker_name]
            pool_stats = worker_stats['stats']['pool']
            running_tasks = pool_stats['writes']['inqueues']['active']
            concurrency = pool_stats['max-concurrency']
            completed_tasks = pool_stats['writes']['total']

            tasks_class = tasks_full if running_tasks == concurrency else tasks_ok
            tasks_html = mark_safe(
                '<span class="label %s">%d / %d</span> :: %d' % (
                    tasks_class, running_tasks, concurrency, completed_tasks
                )
            )
        except KeyError:
            pass

        return tasks_html

    celery_monitoring = getattr(settings, 'CELERY_FLOWER_URL', None)
    worker_status = ""
    if celery_monitoring:
        worker_ok = '<span class="label label-success">OK</span>'
        worker_bad = '<span class="label label-important">Down</span>'

        worker_info = []
        worker_stats = get_stats(celery_monitoring, status_only=True)
        detailed_stats = get_stats(celery_monitoring, refresh=True)
        for worker_name, status in worker_stats.items():
            status_html = mark_safe(worker_ok if status else worker_bad)
            tasks_html = get_task_html(detailed_stats, worker_name)
            worker_info.append(' '.join([worker_name, status_html, tasks_html]))
        worker_status = '<br>'.join(worker_info)
    return mark_safe(worker_status)


def parse_celery_workers(celery_workers):
    """
    Parses the response from the flower get workers api into a list of hosts
    we expect to be running and a list of hosts we expect to be stopped
    """
    expect_stopped = []
    expect_running = filter(
        lambda hostname: not hostname.endswith('_timestamp'),
        celery_workers.keys(),
    )

    timestamped_workers = filter(
        lambda hostname: hostname.endswith('_timestamp'),
        celery_workers.keys(),
    )

    def _strip_timestamp(hostname):
        return '.'.join(hostname.split('.')[:-1])

    timestamped_workers = sorted(timestamped_workers, key=_strip_timestamp)

    for hostname, group in groupby(timestamped_workers, _strip_timestamp):

        sorted_workers = sorted(list(group), reverse=True)
        expect_running.append(sorted_workers.pop(0))
        expect_stopped.extend(sorted_workers)
    return expect_running, expect_stopped
