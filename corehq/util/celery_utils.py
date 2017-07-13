from __future__ import print_function
import multiprocessing
import os

import kombu.five
from celery import Celery
from celery import current_app
from celery.backends.base import DisabledBackend
from celery.task import task
from celery.worker.autoscale import Autoscaler
from django.conf import settings
from djcelery.loaders import DjangoLoader
from datetime import datetime
from time import sleep, time


def no_result_task(*args, **kwargs):
    """
    We use an instance of DatabaseBackend to store results of celery tasks.

    But even with ignore_result=True, celery will still create an entry into
    celery_taskmeta when creating the task because we have the DatabaseBackend
    configured.

    In order to avoid creating an entry into celery_taskmeta, we also need
    to override the task's result backend to be an instance of the DisabledBackend.

    Use this decorator to create tasks for which we don't need to store
    result info.
    """
    kwargs['ignore_result'] = True
    kwargs['backend'] = DisabledBackend(current_app)

    def wrapper(fcn):
        return task(*args, **kwargs)(fcn)

    return wrapper


class TaskInfo(object):

    def __init__(self, _id, name, time_start=None):
        self.id = _id
        self.name = name
        # http://stackoverflow.com/questions/20091505/celery-task-with-a-time-start-attribute-in-1970
        if time_start:
            self.time_start = datetime.fromtimestamp(time() - kombu.five.monotonic() + time_start)
        else:
            self.time_start = None


class InvalidTaskTypeError(Exception):
    pass


def get_active_task_info(tasks):
    result = []
    for task_dict in tasks:
        result.append(TaskInfo(task_dict.get('id'), task_dict.get('name'), task_dict.get('time_start')))
    return result


def get_reserved_task_info(tasks):
    result = []
    for task_dict in tasks:
        result.append(TaskInfo(task_dict.get('id'), task_dict.get('name')))
    return result


def get_scheduled_task_info(tasks):
    result = []
    for task_dict in tasks:
        task_dict = task_dict.get('request', {})
        result.append(TaskInfo(task_dict.get('id'), task_dict.get('name')))
    return result


def _validate_task_state(task_state, allow_active=True, allow_scheduled=True,
        allow_reserved=True, allow_revoked=True):

    allowed_states = []
    if allow_active:
        allowed_states.append('active')

    if allow_scheduled:
        allowed_states.append('scheduled')

    if allow_reserved:
        allowed_states.append('reserved')

    if allow_revoked:
        allowed_states.append('revoked')

    if task_state not in allowed_states:
        raise InvalidTaskTypeError("Task state must be one of: {}".format(allowed_states))


def _get_task_info_fcn(task_state):
    return {
        'active': get_active_task_info,
        'reserved': get_reserved_task_info,
        'scheduled': get_scheduled_task_info,
    }.get(task_state)


def revoke_tasks(task_names, interval=5):
    """
    Constantly polls all workers for any active, reserved, or scheduled
    tasks, and revokes the tasks if they match any of the given task names.

    Note that when reserved or scheduled tasks are revoked, they don't disappear from
    the list of reserved or scheduled tasks immediately. Instead, they will just be
    discarded by the worker when they try to move to active.

    :param task_names: a list of fully qualified task names to revoke
    :param interval: the interval (in seconds) on which to poll the workers for tasks

    Example:
    revoke_tasks(['couchexport.tasks.export_async'])
    """
    app = Celery()
    app.config_from_object(settings)
    task_ids = set()
    while True:
        tasks = []
        inspect = app.control.inspect()
        for task_state in ['active', 'reserved', 'scheduled']:
            result = getattr(inspect, task_state)()
            if not result:
                continue

            for worker, task_dicts in result.iteritems():
                tasks.extend(_get_task_info_fcn(task_state)(task_dicts))

        for task in tasks:
            if task.name in task_names and task.id not in task_ids:
                app.control.revoke(task.id, terminate=True)
                task_ids.add(task.id)
                print(datetime.utcnow(), 'Revoked', task.id, task.name)

        sleep(interval)


def print_tasks(worker, task_state):
    """
    Prints celery tasks that have been received by the given worker that are in the
    given state.

    Examples:
    print_tasks('celery@hqcelery0.internal-va.commcarehq.org_main', 'active')
    print_tasks('celery@hqcelery1.internal-va.commcarehq.org_sms_queue', 'reserved')
    """
    _validate_task_state(task_state)

    app = Celery()
    app.config_from_object(settings)
    inspect = app.control.inspect([worker])
    fcn = getattr(inspect, task_state)
    result = fcn()
    if not result:
        print("Worker does not appear to be online. Check worker name, and that it is running.")
        return

    tasks = result[worker]

    if not tasks:
        print('(none)')
        return

    if task_state == 'revoked':
        for task_id in tasks:
            print(task_id)
        return

    tasks = _get_task_info_fcn(task_state)(tasks)

    for task_info in tasks:
        if task_info.time_start:
            print(task_info.id, task_info.time_start, task_info.name)
        else:
            print(task_info.id, task_info.name)


def get_running_workers(timeout=10):
    app = Celery()
    app.config_from_object(settings)
    result = app.control.ping(timeout=timeout)

    worker_names = []
    for worker_info in result:
        worker_names.extend(worker_info.keys())

    return worker_names


class LoadBasedAutoscaler(Autoscaler):
    def _maybe_scale(self, req=None):
        procs = self.processes
        cur = min(self.qty, self.max_concurrency)

        available_cpus = multiprocessing.cpu_count()
        try:
            load_avgs = os.getloadavg()
            max_avg = max(load_avgs[0], load_avgs[1])
            normalized_load = max_avg / available_cpus
        except OSError:
            # if we can't get the load average, let's just use normal autoscaling
            load_avgs = None
            normalized_load = 0

        if cur > procs and normalized_load < 0.90:
            self.scale_up(cur - procs)
            return True
        elif procs > self.min_concurrency:
            if cur < procs:
                self.scale_down(min(procs - cur, procs - self.min_concurrency))
                return True
            elif normalized_load > 0.90:
                # if load is too high trying scaling down 1 worker at a time.
                # if we're already at minimum concurrency let's just ride it out
                self.scale_down(1)
                return True


class OffPeakLoadBasedAutoscaler(LoadBasedAutoscaler):
    def _is_off_peak(self):
        now = datetime.utcnow().time()
        if settings.OFF_PEAK_TIME:
            time_begin = settings.OFF_PEAK_TIME[0]
            time_end = settings.OFF_PEAK_TIME[1]
            if time_begin < time_end:  # off peak is middle of day
                if time_begin < now < time_end:
                    return True
            else:  # off peak is overnight
                if time_begin < now or now < time_end:
                    return True

        # if this setting isn't set consider us always during peak time
        return False

    def _during_peak_time(self):
        return not self._is_off_peak()

    def _maybe_scale(self, req=None):
        procs = self.processes

        if self._during_peak_time():
            if procs > self.min_concurrency:
                self.scale_down(1)
                return True
            elif procs == self.min_concurrency:
                return False

        super(OffPeakLoadBasedAutoscaler, self)._maybe_scale(req)


class LoadBasedLoader(DjangoLoader):
    def read_configuration(self):
        ret = super(LoadBasedLoader, self).read_configuration()
        ret['CELERYD_AUTOSCALER'] = 'corehq.util.celery_utils:LoadBasedAutoscaler'
        return ret


class OffPeakLoadBasedLoader(DjangoLoader):
    def read_configuration(self):
        ret = super(OffPeakLoadBasedLoader, self).read_configuration()
        ret['CELERYD_AUTOSCALER'] = 'corehq.util.celery_utils:OffPeakLoadBasedAutoscaler'
        return ret
