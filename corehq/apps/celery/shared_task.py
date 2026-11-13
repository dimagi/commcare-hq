from celery import shared_task
from django.conf import settings

from corehq.apps.celery.periodic import PeriodicTask


def task(*args, **kwargs):
    """
    A wrapper over shared_task decorator. You should use this decorator to create celery tasks in HQ.

    This decorator serves multiple purposes:

    - Adds "durable" task functionality that optionally creates a permanent
      record of incomplete tasks
    - enforces the default task serializer as JSON, which is needed until
      https://github.com/celery/celery/issues/6759 is resolved, at which point
      CELERY_TASK_SERIALIZER can be set back to json.

    Parameters:
        serializer (string): Serialization method to use.
        Can be pickle, json, yaml, msgpack or any custom serialization
        method that's been registered with kombu.serialization.registry.

        durable (boolean): If true, creates a TaskRecord object to track a task until it is completed
        by a worker.

        queue (string): Name of the queue in which task is supposed to run

        All other options defined https://docs.celeryq.dev/en/stable/userguide/tasks.html#list-of-options
    """
    # depends on a database model which cannot be imported until the app is registered
    from corehq.apps.celery.durable import DurableTask

    default_queue = getattr(settings, 'CELERY_MAIN_QUEUE', 'celery')
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return shared_task(serializer='json', queue=default_queue)(args[0])

    kwargs.setdefault('serializer', 'json')
    kwargs.setdefault('queue', default_queue)
    kwargs.setdefault('options', {})
    kwargs.setdefault('base', DurableTask)

    if kwargs.get('base') == PeriodicTask:
        kwargs['options']['queue'] = kwargs.get('queue')

    def task(fn):
        return shared_task(*args, **kwargs)(fn)

    return task
