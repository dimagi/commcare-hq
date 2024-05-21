from celery import Task

"""
@periodic_task has been removed from celery>=5.0.0.
This is an implementation of periodic_task based on how they were implemented before
See:
    https://github.com/celery/celery/blob/b2668607c909c61becd151905b4525190c19ff4a/celery/task/base.py#L275
    https://github.com/celery/celery/issues/6707#issuecomment-825542048

"""


class PeriodicTask(Task):

    @classmethod
    def on_bound(cls, app):
        app.conf.beat_schedule[cls.name] = {
            'task': cls.name,
            'schedule': cls.run_every,
            'args': (),
            'kwargs': {},
            'options': cls.options or {}
        }


def periodic_task(**options):
    """Use this decorator to create periodic celery tasks in HQ

        Parameters:
        queue (string): Name of the queue in which task is supposed to run
        run_every (integer|crontab): Accepts
            - integer value which represents the seconds interval in which task will run.
            - celery.schedules.crontab interval
        options (dict): https://docs.celeryq.dev/en/latest/reference/celery.app.task.html#celery.app.task.Task.apply_async # noqa E501
    """
    from corehq.apps.celery.shared_task import task
    return task(base=PeriodicTask, **options)


def periodic_task_when_true(boolean, *args, **kwargs):
    """Register a periodic task only when the first arg evals to True"""
    if boolean:
        return periodic_task(*args, **kwargs)
    else:
        return lambda fn: fn
