
def task(**options):
    """Use this decorator to create celery tasks in HQ

        Parameters:
        serializer (string)(required): Serialization method to use.
         Can be pickle, json, yaml, msgpack or any custom serialization method that's been registered with kombu.serialization.registry.
        queue (string): Name of the queue in which task is supposed to run
        options (dict): https://docs.celeryq.dev/en/latest/reference/celery.app.task.html#celery.app.task.Task.apply_async # noqa E501
    """
    options.setdefault('options', {})
    assert options.get('serializer'), 'Task should be defined with serializer'
    if options.get('queue'):
        options['options']['queue'] = options.pop('queue')
    from corehq.apps.celery import app
    return app.task(**options)
