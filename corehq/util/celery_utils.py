from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime, timedelta
from time import sleep, time

from celery import Celery, current_app
from celery.backends.base import DisabledBackend
from celery.schedules import crontab
from celery.task import task, periodic_task
from django.conf import settings
import kombu.five
import six


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

            for worker, task_dicts in six.iteritems(result):
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
        worker_names.extend(list(worker_info))

    return worker_names


def deserialize_run_every_setting(run_every_setting):
    generic_value_error = ValueError(
        "A run_every setting has to be an int or a dict with a single key: "
        "crontab or timedelta")
    if isinstance(run_every_setting, six.integer_types):
        return run_every_setting
    elif isinstance(run_every_setting, dict):
        if len(run_every_setting) != 1:
            raise generic_value_error
        key, params = list(run_every_setting.items())[0]
        if key == 'crontab':
            fn = crontab
        elif key == 'timedelta':
            fn = timedelta
        else:
            raise generic_value_error
        return fn(**params)
    else:
        raise generic_value_error


def periodic_task_on_envs(envs, *args, **kwargs):
    if settings.SERVER_ENVIRONMENT in envs:
        return periodic_task(*args, **kwargs)
    else:
        return lambda fn: fn
