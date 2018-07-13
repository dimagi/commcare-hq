from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

from ast import literal_eval
from datetime import datetime
from time import sleep, time

from celery import Celery, current_app
from celery.backends.base import DisabledBackend
from celery.task import task
from django.conf import settings
import kombu.five
import six

from soil.progress import get_task_status


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

    @staticmethod
    def parse_timestamp(timestamp):
        if timestamp is None:
            return None
        # http://stackoverflow.com/questions/20091505/celery-task-with-a-time-start-attribute-in-1970
        return datetime.fromtimestamp(time() - kombu.five.monotonic() + timestamp)

    def __init__(self, _id, name, time_start=None):
        self.id = _id
        self.name = name
        self.time_start = self.parse_timestamp(time_start)


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


def _parse_args(task):

    def parse_populate_export_download_task_args(task):
        """
        Parses the parameters of populate_export_download_task() to
        determine which export instances it was called with.

        Returns `task` dict with new key "export_instances". If the
        parameters can't be parsed, `task` is returned as-is.

        (`task` is passed by reference, so the return value can be
        ignored.)
        """
        # task['args'] is a string representation of the args that
        # populate_export_download_task() was called with, and task['kwargs']
        # is the same for its keyword arguments. The parameters of
        # populate_export_download_task() are: export_instance_ids, filters,
        # download_id, filename=None, expiry=10 * 60 * 60
        from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance

        try:
            args = literal_eval(task['args'])
            kwargs = literal_eval(task['kwargs'])
        except (SyntaxError, ValueError):
            pass
        else:
            export_instance_ids = args[0] if args else kwargs['export_instance_ids']
            export_instances = (get_properly_wrapped_export_instance(doc_id) for doc_id in export_instance_ids)
            task['export_instances'] = [{
                'id': inst._id,
                'name': inst.name,
                'domain': inst.domain,
            } for inst in export_instances]
        return task

    def parse_start_export_task_args(task):
        """
        Parses the parameters of start_export_task() to determine the
        export instance is was called with.

        Results are returned in new key `export_instance`.
        """
        # start_export_task() params: export_instance_id, last_access_cutoff
        from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance

        try:
            args = literal_eval(task['args'])
            kwargs = literal_eval(task['kwargs'])
        except (SyntaxError, ValueError):
            pass
        else:
            export_instance_id = kwargs.get('export_instance_id', args[0])
            export_instance = get_properly_wrapped_export_instance(export_instance_id)
            task['export_instance'] = {
                'id': export_instance._id,
                'name': export_instance.name,
                'domain': export_instance.domain,
            }

        return task

    func = {
        'corehq.apps.export.tasks.populate_export_download_task': parse_populate_export_download_task_args,
        'corehq.apps.export.tasks._start_export_task': parse_start_export_task_args,
    }.get(task['name'])
    return func(task) if func else task


def _get_workers(app, queue):
    result = app.control.ping(timeout=0.1)  # Don't wait longer than 0.1s
    return [name for info in result for name in info if queue in name]


def _get_queue_tasks(app, workers):
    inspect = app.control.inspect(workers)
    for worker, tasks in six.iteritems(inspect.active()):
        for task in tasks:
            # Don't use TaskInfo because we need the task's args and
            # kwargs to unpack what the task doing.
            task['state'] = 'active'
            yield task
    for worker, tasks in six.iteritems(inspect.scheduled()):
        for task in tasks:
            task['request']['state'] = 'scheduled'
            yield task['request']
    for worker, tasks in six.iteritems(inspect.reserved()):
        for task in tasks:
            task['state'] = 'reserved'
            yield task


def get_queue_length(queue):
    app = Celery()
    app.config_from_object(settings)
    workers = _get_workers(app, queue)
    if workers:
        return len(list(_get_queue_tasks(app, workers)))


def get_queue_tasks(queue):
    app = Celery()
    app.config_from_object(settings)
    workers = _get_workers(app, queue)
    if workers:
        for task in _get_queue_tasks(app, workers):
            task = _parse_args(task)
            if 'time_start' in task:
                task['time_start'] = TaskInfo.parse_timestamp(task['time_start'])
            async_result = app.AsyncResult(task['id'])
            task['status'] = get_task_status(async_result)
            yield task


def get_task_str(task):
    """
    Return a one-line string representation of a task.
    """
    def get_inst_str(inst):
        return '; '.join((
            'ID: {}'.format(inst['id']),
            'Name: {}'.format(inst['name']),
            'Domain: {}'.format(inst['domain']),
        ))

    if 'export_instances' in task:
        inst_str = '), ('.join((get_inst_str(inst) for inst in task['export_instances']))
    elif 'export_instance' in task:
        inst_str = get_inst_str(task['export_instance'])
    else:
        inst_str = ''
    task_str = '; '.join((
        'Task ID: {}'.format(task['id']),
        'State: {}'.format(task['state']),
        'Status: {}'.format(task['status'].state),
        'Start time: {}'.format(task['start_time'] or 'N/A'),
        'Progress: {}%'.format(task['status'].progress.percent),
        'Error: "{}"'.format(task['status'].progress.error_message or "N/A"),
        'Export instances: [({})]'.format(inst_str),
    ))
    return task_str
