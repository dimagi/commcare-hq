from celery import shared_task


def task(*args, **kwargs):
    """Use this decorator to create celery tasks in HQ

        Parameters:
        serializer (string): Serialization method to use.
         Can be pickle, json, yaml, msgpack or any custom serialization method that's been registered with kombu.serialization.registry.
        queue (string): Name of the queue in which task is supposed to run
        options (dict): https://docs.celeryq.dev/en/latest/reference/celery.app.task.html#celery.app.task.Task.apply_async # noqa E501
    """
    kwargs['serializer'] = kwargs.pop('serializer', 'json')

    def wrapper(fn):
        return shared_task(*args, **kwargs)(fn)

    return wrapper
