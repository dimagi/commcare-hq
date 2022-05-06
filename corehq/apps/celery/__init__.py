from celery import Celery, Task
from django.apps import AppConfig


class Config(AppConfig):
    """Configure global Celery app as part of Django setup"""
    name = 'corehq.apps.celery'

    def __init__(self, *args, **kw):
        _init_celery_app()
        super().__init__(*args, **kw)


def _init_celery_app():
    assert "app" not in globals(), "Celery is already initialized"
    global app
    app = Celery()
    app.config_from_object('django.conf:settings', namespace='CELERY')
    app.autodiscover_tasks()
    app.set_default()


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


def periodic_task(*args, **options):
    if not options.get('options'):
        options['options'] = {}
    if options.get('queue'):
        options['options'].update({
            'queue': options.pop('queue')
        })
    options['base'] = PeriodicTask
    return app.task(**options)
