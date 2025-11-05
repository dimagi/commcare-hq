from django.apps import AppConfig

from celery import Celery
from celery.signals import setup_logging

# Imported to give an idea of where decorators are defined and
# we will be importing these decorators from this file in tasks
from corehq.apps.celery.periodic import (  # noqa F401;
    periodic_task,
    periodic_task_when_true,
)
from corehq.apps.celery.shared_task import task  # noqa F401;


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


@setup_logging.connect()
def config_loggers(*args, **kwargs):
    from logging.config import dictConfig

    from django.conf import settings
    dictConfig(settings.LOGGING)
