
from importlib import import_module
from itertools import groupby

from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.utils.safestring import mark_safe

import requests
from six.moves import filter

from pillowtop.utils import force_seq_int

from corehq.apps.hqadmin.models import HistoricalPillowCheckpoint

EPSILON = 10000000


def check_for_rewind(checkpoint):
    historical_checkpoint = HistoricalPillowCheckpoint.get_historical_max(checkpoint.checkpoint_id)
    if not historical_checkpoint:
        return False
    db_seq = checkpoint.get_current_sequence_id()
    store_seq = historical_checkpoint.seq_int
    has_rewound = force_seq_int(db_seq) < store_seq - EPSILON
    return has_rewound, historical_checkpoint.seq


def get_celery_stats():

    def get_stats(celery_monitoring, status_only=False, refresh=False):
        params = {'refresh': 'true'} if refresh else {}
        if status_only:
            params['status'] = 'true'
        try:
            return requests.get(
                celery_monitoring + '/api/workers',
                params=params,
                timeout=3,
            ).json()
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


def parse_celery_pings(worker_responses):
    pings = {}
    for worker in worker_responses:
        assert len(list(worker)) == 1

        worker_fullname = list(worker)[0]
        pings[worker_fullname] = worker[worker_fullname].get('ok') == 'pong'
    return pings


def parse_celery_workers(celery_workers):
    """
    Parses the response from the flower get workers api into a list of hosts
    we expect to be running and a list of hosts we expect to be stopped
    """
    expect_stopped = []
    expect_running = list(filter(
        lambda hostname: not hostname.endswith('_timestamp'),
        celery_workers,
    ))

    timestamped_workers = list(filter(
        lambda hostname: hostname.endswith('_timestamp'),
        celery_workers,
    ))

    def _strip_timestamp(hostname):
        return '.'.join(hostname.split('.')[:-1])

    timestamped_workers = sorted(timestamped_workers, key=_strip_timestamp)

    for hostname, group in groupby(timestamped_workers, _strip_timestamp):

        sorted_workers = sorted(list(group), reverse=True)
        expect_running.append(sorted_workers.pop(0))
        expect_stopped.extend(sorted_workers)
    return expect_running, expect_stopped


def get_django_user_from_session(session):
    if not session:
        return None

    UserModel = get_user_model()
    try:
        user_id = UserModel._meta.pk.to_python(session[SESSION_KEY])
    except KeyError:
        return None
    else:
        try:
            return UserModel._default_manager.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None


def get_session(session_key):
    engine = import_module(settings.SESSION_ENGINE)
    session = engine.SessionStore(session_key)
    try:
        if session.is_empty():
            return None
    except AttributeError:
        return None

    return session
