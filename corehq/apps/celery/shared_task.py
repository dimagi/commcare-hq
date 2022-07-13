from celery import shared_task


def task(*args, **kwargs):
    """
    A wrapper over shared_task decorator which enforces the default task
    serializer as JSON this decorator to create celery tasks in HQ.

    This is planned to be used until https://github.com/celery/celery/issues/6759 is fixed.
    After the fix goes out
        - feel free to remove it and use the native shared_task decorator
        - Set CELERY_TASK_SERIALIZER back to json

    Parameters:
        serializer (string): Serialization method to use.
        Can be pickle, json, yaml, msgpack or any custom serialization
        method that's been registered with kombu.serialization.registry.

        queue (string): Name of the queue in which task is supposed to run

        All other options defined https://docs.celeryq.dev/en/stable/userguide/tasks.html#list-of-options # noqa E501
    """
    
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return shared_task(serializer='json')(args[0])

    kwargs.setdefault('serializer', 'json')

    def task(fn):
        return shared_task(*args, **kwargs)(fn)

    return task
