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
    if not options.get('options'):
        options['options'] = {}
    if options.get('queue'):
        options['options'].update({
            'queue': options.pop('queue')
        })
    options['base'] = PeriodicTask
    from corehq.apps.celery import app
    return app.task(**options)
